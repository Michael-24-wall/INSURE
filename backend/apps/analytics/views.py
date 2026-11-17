import csv

from django.conf import settings
from django.core.cache import cache
from django.http import StreamingHttpResponse
from django.shortcuts import get_object_or_404
from rest_framework import serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import User
from apps.audit.models import AuditLog
from apps.claims.models import Claim
from apps.common.models import PlatformSetting, is_platform_admin
from apps.common.permissions import IsPlatformAdmin
from apps.common.scoping import user_insurer_ids
from apps.inspections.models import Inspection
from apps.insurance.models import Insurer, Policy, QuotationRequest
from apps.notifications.models import Notification
from apps.payments.models import Payment

from .services import admin_dashboard, customer_dashboard, financial_report, provider_dashboard


def _cached_dashboard(key, fn):
    ttl = int(getattr(settings, "DASHBOARD_CACHE_SECONDS", 60))
    return cache.get_or_set(key, fn, ttl)


class DashboardView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        u = request.user
        if is_platform_admin(u):
            return Response({"role": "admin", "data": _cached_dashboard("dash:admin", admin_dashboard)})
        if u.role == User.Role.CUSTOMER:
            return Response({"role": "customer", "data": _cached_dashboard(f"dash:customer:{u.id}", lambda: customer_dashboard(u))})
        if u.role == User.Role.INSPECTOR:
            qs = Inspection.objects.filter(inspector=u)
            return Response(
                {
                    "role": "inspector",
                    "data": {
                        "assigned": qs.count(),
                        "scheduled": qs.filter(status__in=["scheduled", "in_progress"]).count(),
                        "completed": qs.filter(status="completed").count(),
                        "upcoming": list(
                            qs.filter(status="scheduled")
                            .order_by("scheduled_at")
                            .values("id", "inspection_number", "scheduled_at", "location", "vehicle__registration_number")[:5]
                        ),
                    },
                }
            )
        return Response({"role": u.role, "data": _cached_dashboard(f"dash:provider:{u.id}", lambda: provider_dashboard(u))})


class AdminDashboardView(APIView):
    permission_classes = [IsPlatformAdmin]

    def get(self, request):
        return Response(_cached_dashboard("dash:admin", admin_dashboard))


class FinancialReportView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        insurer_ids = None
        if not is_platform_admin(request.user):
            if request.user.role == User.Role.CUSTOMER:
                return Response({"detail": "Not allowed."}, status=403)
            insurer_ids = user_insurer_ids(request.user)
        return Response(
            financial_report(
                start=request.query_params.get("start"),
                end=request.query_params.get("end"),
                insurer_ids=insurer_ids,
            )
        )


class ProviderPerformanceView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.user.role == User.Role.CUSTOMER:
            return Response({"detail": "Not allowed."}, status=403)
        insurer_ids = None
        if not is_platform_admin(request.user):
            insurer_ids = user_insurer_ids(request.user)
        from django.db.models import Count, Sum

        from apps.insurance.models import Quotation

        qs = Quotation.objects.all()
        if insurer_ids is not None:
            qs = qs.filter(insurer_id__in=insurer_ids)
        data = (
            qs.values("insurer__display_name", "insurer_id", "status")
            .annotate(count=Count("id"), premium=Sum("premium"))
            .order_by("insurer__display_name")
        )
        return Response(list(data))


class AuditLogViewSet(viewsets.ViewSet):
    permission_classes = [IsPlatformAdmin]

    def list(self, request):
        qs = AuditLog.objects.select_related("actor").order_by("-created_at")
        entity = request.query_params.get("entity_type")
        actor = request.query_params.get("actor")
        if entity:
            qs = qs.filter(entity_type=entity)
        if actor:
            qs = qs.filter(actor__email__icontains=actor)
        limit = min(int(request.query_params.get("limit", 100)), 500)
        return Response(
            [
                {
                    "id": str(a.id),
                    "actor": a.actor.email if a.actor else None,
                    "action": a.action,
                    "entity_type": a.entity_type,
                    "entity_id": a.entity_id,
                    "changes": a.changes,
                    "ip_address": a.ip_address,
                    "created_at": a.created_at,
                }
                for a in qs[:limit]
            ]
        )


class PlatformSettingView(APIView):
    permission_classes = [IsPlatformAdmin]

    def get(self, request):
        settings_qs = PlatformSetting.objects.all()
        return Response({s.key: s.value for s in settings_qs})

    def put(self, request):
        if not is_platform_admin(request.user):
            return Response({"detail": "Not allowed."}, status=403)
        key = request.data.get("key")
        value = request.data.get("value")
        if not key:
            return Response({"detail": "key is required."}, status=400)
        setting, _ = PlatformSetting.objects.update_or_create(
            key=key, defaults={"value": value, "description": request.data.get("description", "")}
        )
        return Response({"key": setting.key, "value": setting.value})


class _Echo:
    def write(self, value):
        return value


def _csv_response(filename, header, rows):
    echo = _Echo()

    def generate():
        yield echo.write(",".join(header) + "\r\n")
        for row in rows:
            yield echo.write(",".join('"' + str(v).replace('"', '""') + '"' for v in row) + "\r\n")

    response = StreamingHttpResponse(generate(), content_type="text/csv")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


class ExportView(APIView):
    permission_classes = [IsPlatformAdmin]

    def get(self, request, resource):
        if resource == "payments":
            rows = Payment.objects.select_related("user").values_list(
                "reference", "user__email", "purpose", "amount", "method", "status", "receipt_number", "created_at"
            )
            return _csv_response(
                "payments.csv",
                ["reference", "user", "purpose", "amount", "method", "status", "receipt", "created_at"],
                rows,
            )
        if resource == "policies":
            rows = Policy.objects.select_related("customer", "insurer").values_list(
                "policy_number", "customer__email", "insurer__display_name", "start_date", "end_date", "premium", "status"
            )
            return _csv_response(
                "policies.csv",
                ["policy_number", "customer", "insurer", "start_date", "end_date", "premium", "status"],
                rows,
            )
        if resource == "claims":
            rows = Claim.objects.select_related("customer", "policy").values_list(
                "claim_number", "customer__email", "policy__policy_number", "claim_type", "amount_claimed", "status", "created_at"
            )
            return _csv_response(
                "claims.csv",
                ["claim_number", "customer", "policy", "type", "amount_claimed", "status", "created_at"],
                rows,
            )
        if resource == "users":
            rows = User.objects.values_list("email", "role", "is_active", "email_verified", "created_at")
            return _csv_response(
                "users.csv", ["email", "role", "is_active", "email_verified", "created_at"], rows
            )
        return Response({"detail": "Unknown export resource."}, status=404)
