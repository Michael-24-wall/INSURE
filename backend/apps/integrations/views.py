from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.accounts.models import User
from apps.audit.services import log_action
from apps.common.models import is_platform_admin, user_org_ids
from apps.common.permissions import IsPlatformAdmin
from apps.organizations.models import Organization

from .adapters import safe_test
from .models import Integration, IntegrationLog, WebhookEvent
from .serializers import IntegrationLogSerializer, IntegrationSerializer, WebhookEventSerializer


class IntegrationViewSet(viewsets.ModelViewSet):
    serializer_class = IntegrationSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ["provider_type", "status", "is_enabled", "organization"]
    search_fields = ["name", "base_url", "organization__name"]

    def get_queryset(self):
        if self.request.user.role not in {
            User.Role.PROVIDER_ADMIN,
            User.Role.PROVIDER_STAFF,
            User.Role.ADMIN,
            User.Role.SUPER_ADMIN,
        }:
            raise PermissionDenied("Only provider staff can access integrations.")
        qs = Integration.objects.select_related("organization")
        if is_platform_admin(self.request.user):
            return qs
        return qs.filter(organization_id__in=user_org_ids(self.request.user))

    def _assert_manager(self, organization):
        if is_platform_admin(self.request.user):
            return
        if self.request.user.role != User.Role.PROVIDER_ADMIN:
            raise PermissionDenied("Only provider administrators can manage integrations.")
        if organization.id not in user_org_ids(self.request.user):
            raise PermissionDenied("Not allowed for this organization.")

    def perform_create(self, serializer):
        self._assert_manager(serializer.validated_data["organization"])
        org = serializer.validated_data["organization"]
        if org.organization_type != Organization.Type.INSURER:
            raise ValidationError({"organization": "Integrations are only available for insurer organizations."})
        integration = serializer.save()
        log_action(self.request.user, "integration.created", integration)

    def perform_update(self, serializer):
        self._assert_manager(serializer.instance.organization)
        integration = serializer.save()
        log_action(self.request.user, "integration.updated", integration)

    def perform_destroy(self, instance):
        self._assert_manager(instance.organization)
        log_action(self.request.user, "integration.deleted", instance)
        instance.delete()

    @action(detail=True, methods=["post"])
    def test(self, request, pk=None):
        integration = self.get_object()
        self._assert_manager(integration.organization)
        ok, result = safe_test(integration)
        log_action(request.user, "integration.tested", integration, changes={"ok": ok})
        return Response(
            {"success": ok, "result": result, "status": integration.status},
            status=200 if ok else 400,
        )

    @action(detail=True, methods=["get"], url_path="logs")
    def logs(self, request, pk=None):
        integration = self.get_object()
        qs = integration.logs.all()[:200]
        return Response(IntegrationLogSerializer(qs, many=True).data)


class WebhookEventViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = WebhookEventSerializer
    permission_classes = [IsPlatformAdmin]
    queryset = WebhookEvent.objects.all().order_by("-created_at")
    filterset_fields = ["provider", "processed", "signature_valid"]
