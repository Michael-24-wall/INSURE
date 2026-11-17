from decimal import Decimal

from django.conf import settings
from django.db import transaction
from django.db.models import Count, Min, Q
from django.shortcuts import get_object_or_404
from django.http import FileResponse
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.accounts.models import User
from apps.audit.services import log_action
from apps.common.models import is_platform_admin, user_org_ids
from apps.common.scoping import user_insurer_ids
from apps.common.utils import generate_reference
from apps.notifications.services import notify, notify_many
from apps.organizations.models import Membership, Organization

from .models import Application, CoverageOption, Insurer, Policy, Product, Quotation, QuotationRequest
from .serializers import (
    AgentApplicationCreateSerializer,
    ApplicationSerializer,
    CoverageOptionSerializer,
    DealerApplicationCreateSerializer,
    InsurerSerializer,
    PolicyIssueSerializer,
    PolicySerializer,
    ProductSerializer,
    QuotationCreateSerializer,
    QuotationRequestSerializer,
    QuotationSerializer,
)
from .services import generate_quotes, issue_policy, select_quotation


def org_members(organization, roles=None):
    qs = Membership.objects.filter(organization=organization, is_active=True).select_related("user")
    if roles:
        qs = qs.filter(role__in=roles)
    return [m.user for m in qs]


def notify_quotation_participants(req, title, message):
    """Notify the dealership (when present) and the quotation customer."""
    from apps.business_network.services import notify_org

    if req.dealership_id:
        notify_org(req.dealership, title, message, "quotation", f"/dealer/quotes/{req.id}")
    notify(req.customer, title, message, "quotation", f"/app/quotes/{req.id}")


def assert_directed_insurer(req, user):
    """Ensure a directed dealer request is being handled by its target insurer."""
    if is_platform_admin(user):
        return
    if req.insurer_id is None:
        raise ValidationError("This request is open to multiple insurers. Respond with a quotation instead.")
    if req.insurer_id not in user_insurer_ids(user):
        raise PermissionDenied("This request is directed to another insurer.")


class InsurerViewSet(viewsets.ModelViewSet):
    serializer_class = InsurerSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ["is_active"]
    search_fields = ["display_name", "license_number", "organization__name"]

    def get_queryset(self):
        qs = Insurer.objects.select_related("organization").annotate(
            product_count_ann=Count("products", distinct=True)
        )
        user = self.request.user
        if is_platform_admin(user):
            return qs
        if user.role == User.Role.CUSTOMER:
            return qs.filter(is_active=True, organization__status=Organization.Status.VERIFIED)
        return qs.filter(Q(id__in=user_insurer_ids(user)) | Q(is_active=True, organization__status=Organization.Status.VERIFIED))

    def perform_create(self, serializer):
        if not is_platform_admin(self.request.user):
            raise PermissionDenied("Only administrators can create insurer profiles.")
        serializer.save()

    def perform_update(self, serializer):
        ins = self.get_object()
        if not is_platform_admin(self.request.user) and ins.id not in user_insurer_ids(self.request.user):
            raise PermissionDenied("Not allowed to update this insurer.")
        serializer.save()

    def perform_destroy(self, instance):
        if not is_platform_admin(self.request.user):
            raise PermissionDenied("Only platform administrators can delete insurer profiles.")
        instance.delete()


class ProductViewSet(viewsets.ModelViewSet):
    serializer_class = ProductSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ["category", "is_active", "insurer"]
    search_fields = ["name", "code", "insurer__display_name", "description"]
    ordering_fields = ["created_at", "minimum_premium", "base_premium_rate", "name"]

    def get_queryset(self):
        qs = Product.objects.alive().select_related("insurer", "insurer__organization").prefetch_related("coverage_options")
        user = self.request.user
        if is_platform_admin(user):
            return qs
        if user.role == User.Role.CUSTOMER:
            return qs.filter(
                is_active=True,
                insurer__is_active=True,
                insurer__organization__status=Organization.Status.VERIFIED,
            )
        return qs.filter(
            Q(insurer_id__in=user_insurer_ids(user))
            | Q(is_active=True, insurer__organization__status=Organization.Status.VERIFIED)
        )

    def _own_insurer(self):
        ins = Insurer.objects.filter(organization_id__in=user_org_ids(self.request.user)).first()
        if not ins:
            raise PermissionDenied("You are not attached to an insurer organization.")
        return ins

    def perform_create(self, serializer):
        user = self.request.user
        if user.role not in {User.Role.PROVIDER_ADMIN, User.Role.PROVIDER_STAFF, User.Role.ADMIN, User.Role.SUPER_ADMIN}:
            raise PermissionDenied("Only provider staff can create products.")
        insurer = serializer.validated_data.get("insurer")
        if not is_platform_admin(user):
            insurer = self._own_insurer()
        if not insurer:
            raise ValidationError({"insurer": "Insurer is required."})
        product = serializer.save(insurer=insurer)
        log_action(user, "product.created", product, changes={"name": product.name, "insurer": str(insurer.id)})

    def perform_update(self, serializer):
        product = self.get_object()
        user = self.request.user
        if not is_platform_admin(user) and product.insurer_id not in user_insurer_ids(user):
            raise PermissionDenied("Not allowed to update this product.")
        if not is_platform_admin(user) and "insurer" in serializer.validated_data:
            serializer.validated_data.pop("insurer")
        instance = serializer.save()
        instance.version += 1
        instance.save(update_fields=["version"])
        log_action(user, "product.updated", instance, changes={"version": instance.version})

    def perform_destroy(self, instance):
        if not is_platform_admin(self.request.user) and instance.insurer_id not in user_insurer_ids(self.request.user):
            raise PermissionDenied("Not allowed to delete this product.")
        instance.delete()

    @action(detail=True, methods=["get", "post"], url_path="coverage-options")
    def coverage_options(self, request, pk=None):
        product = self.get_object()
        if request.method == "GET":
            return Response(CoverageOptionSerializer(product.coverage_options.all(), many=True).data)
        if not is_platform_admin(request.user) and product.insurer_id not in user_insurer_ids(request.user):
            raise PermissionDenied("Not allowed.")
        serializer = CoverageOptionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(product=product)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["delete"], url_path=r"coverage-options/(?P<option_id>[^/.]+)")
    def delete_coverage_option(self, request, pk=None, option_id=None):
        product = self.get_object()
        if not is_platform_admin(request.user) and product.insurer_id not in user_insurer_ids(request.user):
            raise PermissionDenied("Not allowed.")
        option = get_object_or_404(CoverageOption, pk=option_id, product=product)
        option.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class QuotationRequestViewSet(viewsets.ModelViewSet):
    serializer_class = QuotationRequestSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ["status", "coverage_type", "vehicle", "dealership", "insurer", "partnership"]
    search_fields = [
        "request_number", "vehicle__registration_number", "customer__email",
        "customer__first_name", "customer__last_name", "dealership__name",
    ]
    ordering_fields = ["created_at", "status", "expires_at"]
    http_method_names = ["get", "post", "patch", "head", "options"]

    def _dealer_org(self):
        from apps.business_network.services import user_dealer_org

        return user_dealer_org(self.request.user)

    def _assert_request_participant(self, req, user):
        if is_platform_admin(user) or req.customer_id == user.id:
            return
        dealer_org = self._dealer_org()
        if dealer_org and req.dealership_id == dealer_org.id:
            return
        raise PermissionDenied("Not allowed.")

    def get_queryset(self):
        qs = QuotationRequest.objects.select_related(
            "customer", "vehicle", "product", "insurer", "dealership"
        ).annotate(
            quotation_count_ann=Count("quotations", distinct=True),
            lowest_premium_ann=Min("quotations__premium"),
        )
        user = self.request.user
        if is_platform_admin(user):
            scoped = qs
        elif user.role == User.Role.CUSTOMER:
            scoped = qs.filter(customer=user)
        else:
            dealer_org = self._dealer_org()
            if dealer_org:
                scoped = qs.filter(dealership=dealer_org)
            elif user.role in {User.Role.PROVIDER_ADMIN, User.Role.PROVIDER_STAFF}:
                insurer_ids = user_insurer_ids(user)
                scoped = qs.filter(
                    Q(insurer_id__in=insurer_ids)
                    | Q(
                        insurer__isnull=True,
                        dealership__isnull=True,
                        status__in=[
                            QuotationRequest.Status.PENDING,
                            QuotationRequest.Status.QUOTED,
                            QuotationRequest.Status.SELECTED,
                        ],
                    )
                    | Q(quotations__insurer_id__in=insurer_ids)
                ).distinct()
            else:
                # Agents/other staff retain the read-only open marketplace view.
                scoped = qs.filter(
                    insurer__isnull=True,
                    dealership__isnull=True,
                    status__in=[
                        QuotationRequest.Status.PENDING,
                        QuotationRequest.Status.QUOTED,
                        QuotationRequest.Status.SELECTED,
                    ],
                )

        params = self.request.query_params
        if params.get("created_after"):
            scoped = scoped.filter(created_at__date__gte=params["created_after"])
        if params.get("created_before"):
            scoped = scoped.filter(created_at__date__lte=params["created_before"])
        return scoped.order_by("-created_at")

    def perform_create(self, serializer):
        if self.request.user.role != User.Role.CUSTOMER and not is_platform_admin(self.request.user):
            raise PermissionDenied("Only customers can request quotations.")
        req = serializer.save(
            customer=self.request.user,
            request_number=generate_reference("QR", 10),
            expires_at=timezone.now() + timezone.timedelta(days=14),
        )
        generate_quotes(req)
        from apps.common.utils import safe_enqueue
        from apps.insurance.tasks import push_quotation_request_to_integrations

        transaction.on_commit(lambda: safe_enqueue(push_quotation_request_to_integrations, req.id))
        log_action(self.request.user, "quotation_request.created", req)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        detail = self.get_serializer(serializer.instance).data
        detail["quotations"] = QuotationSerializer(serializer.instance.quotations.all(), many=True).data
        return Response(detail, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        obj = self.get_object()
        if not is_platform_admin(request.user) and obj.customer_id != request.user.id:
            raise PermissionDenied("Not allowed.")
        if obj.status not in {QuotationRequest.Status.PENDING, QuotationRequest.Status.QUOTED}:
            raise ValidationError("This request can no longer be modified.")
        return super().update(request, *args, **kwargs)

    @action(detail=True, methods=["get"], url_path="quotations")
    def quotations(self, request, pk=None):
        req = self.get_object()
        qs = req.quotations.all()
        if not is_platform_admin(request.user) and request.user.role != User.Role.CUSTOMER:
            from apps.business_network.services import user_dealer_org

            dealer_org = user_dealer_org(request.user)
            if not dealer_org or req.dealership_id != dealer_org.id:
                qs = qs.filter(insurer_id__in=user_insurer_ids(request.user))
        return Response(QuotationSerializer(qs, many=True).data)

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        req = self.get_object()
        if not is_platform_admin(request.user) and req.customer_id != request.user.id:
            raise PermissionDenied("Not allowed.")
        if req.status in {QuotationRequest.Status.CONVERTED}:
            raise ValidationError("A converted request cannot be cancelled.")
        req.status = QuotationRequest.Status.CANCELLED
        req.save(update_fields=["status"])
        log_action(request.user, "quotation_request.cancelled", req)
        return Response(QuotationRequestSerializer(req).data)

    @action(detail=True, methods=["post"], url_path="start-review")
    def start_review(self, request, pk=None):
        req = self.get_object()
        assert_directed_insurer(req, request.user)
        if req.status not in {
            QuotationRequest.Status.PENDING,
            QuotationRequest.Status.UNDER_REVIEW,
            QuotationRequest.Status.MORE_INFO,
            QuotationRequest.Status.QUOTED,
        }:
            raise ValidationError("This request is not awaiting review.")
        req.status = QuotationRequest.Status.UNDER_REVIEW
        req.reviewed_by = request.user
        req.reviewed_at = timezone.now()
        req.save(update_fields=["status", "reviewed_by", "reviewed_at"])
        insurer_name = req.insurer.display_name if req.insurer else "the insurer"
        notify_quotation_participants(
            req, "Quotation request under review",
            f"{req.request_number} is being reviewed by {insurer_name}.",
        )
        log_action(request.user, "quotation_request.review_started", req)
        return Response(QuotationRequestSerializer(req).data)

    @action(detail=True, methods=["post"], url_path="request-info")
    def request_info(self, request, pk=None):
        req = self.get_object()
        assert_directed_insurer(req, request.user)
        notes = (request.data.get("notes") or "").strip()
        if not notes:
            raise ValidationError({"notes": "Describe the information required."})
        if req.status not in {
            QuotationRequest.Status.PENDING,
            QuotationRequest.Status.UNDER_REVIEW,
            QuotationRequest.Status.MORE_INFO,
            QuotationRequest.Status.QUOTED,
        }:
            raise ValidationError("Information can no longer be requested on this request.")
        req.status = QuotationRequest.Status.MORE_INFO
        req.insurer_notes = notes
        req.reviewed_by = request.user
        req.reviewed_at = timezone.now()
        req.save(update_fields=["status", "insurer_notes", "reviewed_by", "reviewed_at"])
        notify_quotation_participants(req, "More information required", notes)
        log_action(request.user, "quotation_request.info_requested", req, changes={"notes": notes})
        return Response(QuotationRequestSerializer(req).data)

    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        req = self.get_object()
        assert_directed_insurer(req, request.user)
        reason = (request.data.get("notes") or "").strip()
        if not reason:
            raise ValidationError({"notes": "A rejection reason is required."})
        if req.status in {
            QuotationRequest.Status.CONVERTED,
            QuotationRequest.Status.CANCELLED,
            QuotationRequest.Status.EXPIRED,
            QuotationRequest.Status.REJECTED,
        }:
            raise ValidationError("This request can no longer be rejected.")
        req.status = QuotationRequest.Status.REJECTED
        req.insurer_notes = reason
        req.reviewed_by = request.user
        req.reviewed_at = timezone.now()
        req.save(update_fields=["status", "insurer_notes", "reviewed_by", "reviewed_at"])
        if req.insurer_id:
            req.quotations.filter(insurer_id=req.insurer_id).update(status=Quotation.Status.REJECTED)
        notify_quotation_participants(req, "Quotation request declined", reason)
        log_action(request.user, "quotation_request.rejected", req, changes={"reason": reason})
        return Response(QuotationRequestSerializer(req).data)

    @action(detail=True, methods=["post"])
    def clarify(self, request, pk=None):
        req = self.get_object()
        self._assert_request_participant(req, request.user)
        note = (request.data.get("notes") or "").strip()
        if not note:
            raise ValidationError({"notes": "Describe the clarification you need."})
        if req.status in {
            QuotationRequest.Status.CONVERTED,
            QuotationRequest.Status.CANCELLED,
            QuotationRequest.Status.EXPIRED,
            QuotationRequest.Status.REJECTED,
            QuotationRequest.Status.SELECTED,
        }:
            raise ValidationError("Clarification can no longer be requested on this request.")
        req.clarification_note = note
        req.clarification_requested_at = timezone.now()
        req.save(update_fields=["clarification_note", "clarification_requested_at"])
        from apps.business_network.services import notify_org

        message = f"{req.request_number}: {note}"
        if req.insurer_id:
            notify_org(req.insurer.organization, "Clarification requested", message, "quotation", f"/provider/quotes/{req.id}")
        else:
            notified = set()
            for insurer in req.quotations.select_related("insurer__organization"):
                if insurer.insurer.organization_id in notified:
                    continue
                notified.add(insurer.insurer.organization_id)
                notify_org(
                    insurer.insurer.organization, "Clarification requested", message,
                    "quotation", f"/provider/quotes/{req.id}",
                )
        log_action(request.user, "quotation_request.clarification_requested", req, changes={"notes": note})
        return Response(QuotationRequestSerializer(req).data)


class QuotationViewSet(viewsets.ModelViewSet):
    serializer_class = QuotationSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ["status", "insurer", "request", "source"]
    ordering_fields = ["premium", "created_at"]
    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_queryset(self):
        qs = Quotation.objects.select_related(
            "request", "request__vehicle", "request__customer", "insurer", "product", "application"
        ).prefetch_related("product__coverage_options")
        user = self.request.user
        if is_platform_admin(user):
            return qs
        if user.role == User.Role.CUSTOMER:
            return qs.filter(request__customer=user)
        from apps.business_network.services import user_dealer_org

        dealer_org = user_dealer_org(user)
        if dealer_org:
            return qs.filter(request__dealership=dealer_org)
        return qs.filter(insurer_id__in=user_insurer_ids(user))

    def create(self, request, *args, **kwargs):
        if request.user.role not in {User.Role.PROVIDER_ADMIN, User.Role.PROVIDER_STAFF, User.Role.ADMIN, User.Role.SUPER_ADMIN}:
            raise PermissionDenied("Only provider staff can submit quotations.")
        serializer = QuotationCreateSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        product = data["product"]
        insurer = product.insurer
        if not is_platform_admin(request.user) and insurer.id not in user_insurer_ids(request.user):
            raise PermissionDenied("Product does not belong to your insurer.")
        qreq = data["request"]
        if qreq.insurer_id and qreq.insurer_id != insurer.id:
            raise PermissionDenied("This request is directed to another insurer.")
        if qreq.is_expired:
            raise ValidationError("This quotation request has expired.")
        if qreq.status not in {
            QuotationRequest.Status.PENDING,
            QuotationRequest.Status.UNDER_REVIEW,
            QuotationRequest.Status.MORE_INFO,
            QuotationRequest.Status.QUOTED,
        }:
            raise ValidationError("This quotation request is no longer open.")
        if product.category != qreq.coverage_type:
            raise ValidationError({"product": "Product category must match the requested coverage type."})
        if Quotation.objects.filter(request=qreq, insurer=insurer, product=product).exists():
            raise ValidationError("A quotation for this product already exists on the request.")
        quotation = Quotation.objects.create(
            quotation_number=generate_reference("QT", 10),
            request=qreq,
            insurer=insurer,
            product=product,
            sum_insured=qreq.sum_insured,
            premium=data["premium"],
            taxes=data.get("taxes", Decimal("0.00")),
            fees=data.get("fees", Decimal("0.00")),
            other_charges=data.get("other_charges", Decimal("0.00")),
            excess_amount=data["excess_amount"],
            benefits=data.get("benefits") or product.benefits,
            exclusions=data.get("exclusions") or product.exclusions,
            coverage_limits=data.get("coverage_limits") or {},
            deductibles=data.get("deductibles") or {},
            terms=data.get("terms") if data.get("terms") is not None else product.terms,
            valid_until=data.get("expires_at") or timezone.now() + timezone.timedelta(days=data.get("valid_days", 14)),
            source=Quotation.Source.PROVIDER_API,
            notes=data.get("notes", ""),
        )
        if qreq.status in {QuotationRequest.Status.PENDING, QuotationRequest.Status.UNDER_REVIEW, QuotationRequest.Status.MORE_INFO}:
            qreq.status = QuotationRequest.Status.QUOTED
            qreq.save(update_fields=["status"])
        notify_quotation_participants(
            qreq, "New quotation received",
            f"{insurer.display_name} submitted a quotation for {qreq.request_number}.",
        )
        log_action(request.user, "quotation.created", quotation)
        return Response(QuotationSerializer(quotation).data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        obj = self.get_object()
        if not is_platform_admin(request.user) and obj.insurer_id not in user_insurer_ids(request.user):
            raise PermissionDenied("Not allowed.")
        if obj.status not in {Quotation.Status.RECEIVED, Quotation.Status.MORE_INFO}:
            raise ValidationError("This quotation can no longer be modified.")
        response = super().update(request, *args, **kwargs)
        if obj.status == Quotation.Status.MORE_INFO:
            obj.status = Quotation.Status.RECEIVED
            obj.save(update_fields=["status"])
            response.data["status"] = Quotation.Status.RECEIVED
        log_action(request.user, "quotation.updated", obj)
        return response

    def _assert_insurer_quote(self, request, quotation):
        if not is_platform_admin(request.user) and request.user.role not in {
            User.Role.PROVIDER_ADMIN,
            User.Role.PROVIDER_STAFF,
            User.Role.ADMIN,
            User.Role.SUPER_ADMIN,
        }:
            raise PermissionDenied("Only authorised insurer staff can action this quotation.")
        if not is_platform_admin(request.user) and quotation.insurer_id not in user_insurer_ids(request.user):
            raise PermissionDenied("Not allowed for this insurer.")

    @action(detail=True, methods=["post"])
    def select(self, request, pk=None):
        quotation = self.get_object()
        qreq = quotation.request
        is_customer = qreq.customer_id == request.user.id
        from apps.business_network.services import user_dealer_org

        dealer_org = user_dealer_org(request.user)
        is_dealer = bool(dealer_org and qreq.dealership_id == dealer_org.id)
        if not (is_customer or is_dealer or is_platform_admin(request.user)):
            raise PermissionDenied("Only the requesting customer or dealership can select a quotation.")
        if quotation.valid_until < timezone.now():
            raise ValidationError("This quotation has expired.")
        if quotation.status == Quotation.Status.EXPIRED:
            raise ValidationError("This quotation has expired.")
        if quotation.status == Quotation.Status.REJECTED:
            raise ValidationError("This quotation was withdrawn and cannot be accepted.")
        if quotation.status not in {Quotation.Status.RECEIVED, Quotation.Status.SELECTED}:
            raise ValidationError("This quotation is not available for acceptance.")
        if qreq.is_expired:
            raise ValidationError("The quotation request has expired.")
        if qreq.status in {
            QuotationRequest.Status.CONVERTED,
            QuotationRequest.Status.EXPIRED,
            QuotationRequest.Status.CANCELLED,
            QuotationRequest.Status.REJECTED,
        }:
            raise ValidationError("This request can no longer be selected.")
        select_quotation(quotation)
        notify_quotation_participants(
            qreq, "Quotation selected",
            f"{quotation.insurer.display_name} was selected for {qreq.request_number}.",
        )
        from apps.business_network.services import notify_org

        notify_org(
            quotation.insurer.organization,
            "Quotation selected",
            f"Your quotation for {qreq.request_number} was selected.",
            "quotation",
            f"/provider/quotes/{qreq.id}",
        )
        log_action(request.user, "quotation.selected", quotation)
        return Response(QuotationSerializer(quotation).data)

    @action(detail=True, methods=["post"])
    def decline(self, request, pk=None):
        quotation = self.get_object()
        qreq = quotation.request
        is_customer = qreq.customer_id == request.user.id
        from apps.business_network.services import notify_org, user_dealer_org

        dealer_org = user_dealer_org(request.user)
        is_dealer = bool(dealer_org and qreq.dealership_id == dealer_org.id)
        if not (is_customer or is_dealer or is_platform_admin(request.user)):
            raise PermissionDenied("Only the requesting customer or dealership can decline a quotation.")
        reason = (request.data.get("notes") or "").strip()
        if not reason:
            raise ValidationError({"notes": "A reason for declining is required."})
        if quotation.valid_until < timezone.now() or quotation.status == Quotation.Status.EXPIRED:
            raise ValidationError("This quotation has expired.")
        if quotation.status not in {Quotation.Status.RECEIVED, Quotation.Status.MORE_INFO}:
            raise ValidationError("This quotation can no longer be declined.")
        if qreq.status in {
            QuotationRequest.Status.CONVERTED,
            QuotationRequest.Status.EXPIRED,
            QuotationRequest.Status.CANCELLED,
            QuotationRequest.Status.REJECTED,
            QuotationRequest.Status.SELECTED,
        }:
            raise ValidationError("This request can no longer be declined.")
        quotation.status = Quotation.Status.REJECTED
        quotation.notes = reason
        quotation.save(update_fields=["status", "notes"])
        notify_org(
            quotation.insurer.organization,
            "Quotation declined",
            f"{qreq.request_number}: {reason}",
            "quotation",
            f"/provider/quotes/{qreq.id}",
        )
        notify_quotation_participants(
            qreq, "Quotation declined",
            f"{quotation.insurer.display_name} offer was declined.",
        )
        log_action(request.user, "quotation.declined_by_participant", quotation, changes={"reason": reason})
        return Response(QuotationSerializer(quotation).data)

    @action(detail=True, methods=["post"], url_path="request-info")
    def request_info(self, request, pk=None):
        quotation = self.get_object()
        self._assert_insurer_quote(request, quotation)
        notes = (request.data.get("notes") or "").strip()
        if not notes:
            raise ValidationError({"notes": "Describe the information required."})
        if quotation.status not in {Quotation.Status.RECEIVED, Quotation.Status.MORE_INFO}:
            raise ValidationError("Information can no longer be requested on this quotation.")
        quotation.status = Quotation.Status.MORE_INFO
        quotation.notes = notes
        quotation.save(update_fields=["status", "notes"])
        notify_quotation_participants(
            quotation.request, "More information required", notes,
        )
        log_action(request.user, "quotation.info_requested", quotation, changes={"notes": notes})
        return Response(QuotationSerializer(quotation).data)

    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        quotation = self.get_object()
        self._assert_insurer_quote(request, quotation)
        reason = (request.data.get("notes") or "").strip()
        if not reason:
            raise ValidationError({"notes": "A rejection reason is required."})
        if quotation.status not in {
            Quotation.Status.RECEIVED,
            Quotation.Status.MORE_INFO,
        }:
            raise ValidationError("This quotation can no longer be rejected.")
        quotation.status = Quotation.Status.REJECTED
        quotation.notes = reason
        quotation.save(update_fields=["status", "notes"])
        notify_quotation_participants(
            quotation.request, "Quotation declined", reason,
        )
        log_action(request.user, "quotation.rejected", quotation, changes={"reason": reason})
        return Response(QuotationSerializer(quotation).data)


class ApplicationViewSet(viewsets.ModelViewSet):
    serializer_class = ApplicationSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ["status", "vehicle"]
    search_fields = ["application_number", "customer__email", "vehicle__registration_number"]
    ordering_fields = ["created_at", "status"]
    http_method_names = ["get", "post", "head", "options"]

    def get_queryset(self):
        qs = Application.objects.select_related(
            "customer", "vehicle", "quotation", "quotation__insurer", "quotation__product"
        )
        user = self.request.user
        if is_platform_admin(user):
            return qs
        if user.role == User.Role.CUSTOMER:
            return qs.filter(customer=user)
        from apps.business_network.services import user_dealer_org

        dealer_org = user_dealer_org(user)
        if dealer_org:
            return qs.filter(dealership=dealer_org)
        return qs.filter(quotation__insurer_id__in=user_insurer_ids(user))

    def perform_create(self, serializer):
        if self.request.user.role != User.Role.CUSTOMER and not is_platform_admin(self.request.user):
            raise PermissionDenied("Only customers can create applications.")
        app = serializer.save()
        log_action(self.request.user, "application.created", app)
        notify(
            app.customer,
            "Application draft created",
            f"Application {app.application_number} is ready to submit.",
            "application",
            f"/customer/applications/{app.id}",
        )

    @action(detail=False, methods=["post"], url_path="agent-create")
    def agent_create(self, request):
        if request.user.role not in {
            User.Role.AGENT,
            User.Role.PROVIDER_ADMIN,
            User.Role.PROVIDER_STAFF,
            User.Role.ADMIN,
            User.Role.SUPER_ADMIN,
        }:
            raise PermissionDenied("Only agents and provider staff can create applications for customers.")
        serializer = AgentApplicationCreateSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        customer = data["customer"]
        quotation = data["quotation"]
        agent = data.get("agent") or (request.user if request.user.role == User.Role.AGENT else None)
        qreq = quotation.request
        application = Application.objects.create(
            application_number=generate_reference("APP", 10),
            customer=customer,
            quotation=quotation,
            vehicle=qreq.vehicle,
            agent=agent,
            dealership=qreq.dealership,
            dealership_branch=qreq.dealership_branch,
            partnership=qreq.partnership,
        )
        qreq.status = QuotationRequest.Status.CONVERTED
        qreq.save(update_fields=["status"])
        notify(
            customer,
            "Application started on your behalf",
            f"{request.user.full_name} started application {application.application_number} for you.",
            "application",
            f"/customer/applications/{application.id}",
        )
        log_action(
            request.user,
            "application.agent_created",
            application,
            changes={"customer": str(customer.id), "agent": str(agent.id) if agent else None},
        )
        return Response(ApplicationSerializer(application).data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=["post"], url_path="dealer-create")
    def dealer_create(self, request):
        from apps.business_network.services import user_dealer_org

        dealer_org = user_dealer_org(request.user)
        if not dealer_org and not is_platform_admin(request.user):
            raise PermissionDenied("Only dealership users can start dealer applications.")
        quoted_id = request.data.get("quotation")
        if quoted_id and dealer_org and not is_platform_admin(request.user):
            from django.core.exceptions import ValidationError as DjangoValidationError

            try:
                owned = Quotation.objects.filter(pk=quoted_id, request__dealership=dealer_org).exists()
            except (DjangoValidationError, ValueError):
                owned = False
            if not owned:
                raise PermissionDenied("This quotation does not belong to your dealership.")
        serializer = DealerApplicationCreateSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        quotation = serializer.validated_data["quotation"]
        qreq = quotation.request
        if not is_platform_admin(request.user) and qreq.dealership_id != dealer_org.id:
            raise PermissionDenied("This quotation does not belong to your dealership.")
        application = Application.objects.create(
            application_number=generate_reference("APP", 10),
            customer=qreq.customer,
            quotation=quotation,
            vehicle=qreq.vehicle,
            status=Application.Status.SUBMITTED,
            submitted_at=timezone.now(),
            dealership=qreq.dealership,
            dealership_branch=qreq.dealership_branch,
            partnership=qreq.partnership,
        )
        qreq.status = QuotationRequest.Status.CONVERTED
        qreq.save(update_fields=["status"])
        notify(
            qreq.customer,
            "Application started by your dealership",
            f"Application {application.application_number} was started for {qreq.vehicle.registration_number}.",
            "application",
            f"/app/applications/{application.id}",
        )
        self._notify_insurer(
            application,
            "New dealer application",
            f"{application.application_number} was submitted by a dealership for {application.vehicle.registration_number}.",
        )
        log_action(
            request.user,
            "application.dealer_created",
            application,
            changes={"dealership": str(qreq.dealership_id)},
        )
        return Response(ApplicationSerializer(application).data, status=status.HTTP_201_CREATED)

    def _notify_insurer(self, application, title, message):
        org = application.quotation.insurer.organization
        for u in org_members(org):
            notify(u, title, message, "application", f"/provider/applications/{application.id}")

    @action(detail=True, methods=["post"])
    def submit(self, request, pk=None):
        app = self.get_object()
        if app.customer_id != request.user.id and not is_platform_admin(request.user):
            raise PermissionDenied("Only the applicant can submit.")
        if app.status != Application.Status.DRAFT:
            raise ValidationError("Only draft applications can be submitted.")
        if app.quotation.valid_until < timezone.now():
            raise ValidationError("The underlying quotation has expired.")
        app.status = Application.Status.SUBMITTED
        app.submitted_at = timezone.now()
        app.save(update_fields=["status", "submitted_at"])
        self._notify_insurer(
            app,
            "New insurance application",
            f"{app.application_number} was submitted for {app.vehicle.registration_number}.",
        )
        log_action(request.user, "application.submitted", app)
        return Response(ApplicationSerializer(app).data)

    @action(detail=True, methods=["post"])
    def withdraw(self, request, pk=None):
        app = self.get_object()
        if app.customer_id != request.user.id and not is_platform_admin(request.user):
            raise PermissionDenied("Only the applicant can withdraw.")
        if app.status in {Application.Status.POLICY_ISSUED, Application.Status.REJECTED}:
            raise ValidationError("This application can no longer be withdrawn.")
        app.status = Application.Status.WITHDRAWN
        app.save(update_fields=["status"])
        log_action(request.user, "application.withdrawn", app)
        return Response(ApplicationSerializer(app).data)

    def _provider_action(self, request, app):
        if request.user.role not in {
            User.Role.PROVIDER_ADMIN,
            User.Role.PROVIDER_STAFF,
            User.Role.ADMIN,
            User.Role.SUPER_ADMIN,
        }:
            raise PermissionDenied("Only authorised insurer staff can make underwriting decisions.")
        if not is_platform_admin(request.user) and app.quotation.insurer_id not in user_insurer_ids(request.user):
            raise PermissionDenied("Not allowed for this insurer.")

    @action(detail=True, methods=["post"], url_path="start-review")
    def start_review(self, request, pk=None):
        app = self.get_object()
        self._provider_action(request, app)
        if app.status not in {Application.Status.SUBMITTED, Application.Status.MORE_INFO}:
            raise ValidationError("Application is not awaiting review.")
        app.status = Application.Status.UNDER_REVIEW
        app.reviewed_by = request.user
        app.reviewed_at = timezone.now()
        app.save(update_fields=["status", "reviewed_by", "reviewed_at"])
        notify(app.customer, "Application under review", f"{app.application_number} is being reviewed.", "application")
        log_action(request.user, "application.review_started", app)
        return Response(ApplicationSerializer(app).data)

    @action(detail=True, methods=["post"], url_path="request-info")
    def request_info(self, request, pk=None):
        app = self.get_object()
        self._provider_action(request, app)
        notes = (request.data.get("notes") or "").strip()
        if not notes:
            raise ValidationError({"notes": "Describe the information required."})
        if app.status not in {Application.Status.SUBMITTED, Application.Status.UNDER_REVIEW, Application.Status.MORE_INFO}:
            raise ValidationError("Information can no longer be requested on this application.")
        app.status = Application.Status.MORE_INFO
        app.review_notes = notes
        app.reviewed_by = request.user
        app.reviewed_at = timezone.now()
        app.save(update_fields=["status", "review_notes", "reviewed_by", "reviewed_at"])
        notify(app.customer, "More information required", notes, "application")
        log_action(request.user, "application.info_requested", app, changes={"notes": notes})
        return Response(ApplicationSerializer(app).data)

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        app = self.get_object()
        self._provider_action(request, app)
        if app.status not in {Application.Status.SUBMITTED, Application.Status.UNDER_REVIEW, Application.Status.MORE_INFO}:
            raise ValidationError("Application cannot be approved in its current state.")
        app.status = Application.Status.APPROVED
        app.reviewed_by = request.user
        app.reviewed_at = timezone.now()
        app.review_notes = request.data.get("notes", app.review_notes)
        app.save(update_fields=["status", "reviewed_by", "reviewed_at", "review_notes"])
        notify(app.customer, "Application approved", f"{app.application_number} has been approved. Complete payment to receive your policy.", "application")
        log_action(request.user, "application.approved", app, changes={"notes": app.review_notes})
        return Response(ApplicationSerializer(app).data)

    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        app = self.get_object()
        self._provider_action(request, app)
        reason = (request.data.get("notes") or "").strip()
        if not reason:
            raise ValidationError({"notes": "A rejection reason is required."})
        if app.status not in {
            Application.Status.SUBMITTED,
            Application.Status.UNDER_REVIEW,
            Application.Status.MORE_INFO,
            Application.Status.APPROVED,
        }:
            raise ValidationError("This application can no longer be rejected.")
        app.status = Application.Status.REJECTED
        app.reviewed_by = request.user
        app.reviewed_at = timezone.now()
        app.review_notes = reason
        app.save(update_fields=["status", "reviewed_by", "reviewed_at", "review_notes"])
        notify(app.customer, "Application rejected", reason, "application", f"/app/applications/{app.id}")
        log_action(request.user, "application.rejected", app, changes={"reason": reason})
        return Response(ApplicationSerializer(app).data)

    @action(detail=True, methods=["post"], url_path="issue-policy")
    def issue_policy_action(self, request, pk=None):
        app = self.get_object()
        self._provider_action(request, app)
        if app.status != Application.Status.APPROVED:
            raise ValidationError("The application must be approved by the insurer before a policy can be issued.")
        if not is_platform_admin(request.user):
            from apps.payments.models import Payment

            paid = Payment.objects.filter(
                application=app, purpose=Payment.Purpose.PREMIUM, status=Payment.Status.SUCCEEDED,
                verified_at__isnull=False,
            ).exists()
            if not paid:
                raise ValidationError("A verified premium payment is required before issuing the policy.")
        if settings.KYC_REQUIRED_FOR_POLICY_ISSUANCE:
            from apps.accounts.models import CustomerProfile

            profile = CustomerProfile.objects.filter(user=app.customer).first()
            if not profile or profile.kyc_status != "verified":
                raise ValidationError("The policyholder's identity (KYC) must be verified before the policy can be issued.")
        serializer = PolicyIssueSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            policy = issue_policy(app, request.user, **serializer.validated_data)
        except ValueError as exc:
            raise ValidationError(str(exc))
        notify(
            app.customer,
            "Policy issued",
            f"Policy {policy.policy_number} has been issued for {app.vehicle.registration_number}.",
            "policy",
            f"/customer/policies/{policy.id}",
        )
        log_action(request.user, "policy.issued", policy, changes={"policy_number": policy.policy_number})
        return Response(PolicySerializer(policy).data, status=status.HTTP_201_CREATED)


class PolicyViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = PolicySerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ["status", "insurer", "product"]
    search_fields = ["policy_number", "customer__email", "vehicle__registration_number"]
    ordering_fields = ["created_at", "end_date", "premium"]

    def get_queryset(self):
        qs = Policy.objects.select_related("customer", "insurer", "product", "vehicle").annotate(
            claim_count_ann=Count("claims", distinct=True)
        ).order_by("-created_at")
        user = self.request.user
        if is_platform_admin(user):
            return qs
        if user.role == User.Role.CUSTOMER:
            return qs.filter(customer=user)
        return qs.filter(insurer_id__in=user_insurer_ids(user))

    @action(detail=True, methods=["post"])
    def renew(self, request, pk=None):
        policy = self.get_object()
        if policy.customer_id != request.user.id and not is_platform_admin(request.user):
            raise PermissionDenied("Only the policyholder can request renewal.")
        req = QuotationRequest.objects.create(
            request_number=generate_reference("QR", 10),
            customer=policy.customer,
            vehicle=policy.vehicle,
            product=policy.product,
            coverage_type=policy.product.category,
            sum_insured=policy.sum_insured,
            desired_start_date=max(policy.end_date, timezone.now().date()),
            notes=f"Renewal of policy {policy.policy_number}",
            expires_at=timezone.now() + timezone.timedelta(days=14),
        )
        generate_quotes(req)
        log_action(request.user, "policy.renewal_requested", policy)
        data = QuotationRequestSerializer(req).data
        data["quotations"] = QuotationSerializer(req.quotations.all(), many=True).data
        return Response(data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["get"], url_path="document")
    def document(self, request, pk=None):
        policy = self.get_object()
        if not policy.certificate:
            raise ValidationError("No policy certificate is available for this policy.")
        user = request.user
        if not (
            is_platform_admin(user)
            or policy.customer_id == user.id
            or policy.insurer_id in user_insurer_ids(user)
        ):
            raise PermissionDenied("Not allowed to access this policy document.")
        file = policy.certificate.open("rb")
        return FileResponse(
            file,
            content_type="application/pdf",
            as_attachment=False,
            filename=f"{policy.policy_number}.pdf",
        )
