from django.db import transaction
from django.db.models import Count
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.accounts.models import AgentProfile, InspectorProfile, User
from apps.audit.services import log_action
from apps.common.files import protected_file_response
from apps.common.models import is_platform_admin, user_org_ids
from apps.common.permissions import IsPlatformAdmin
from apps.notifications.services import notify

from .models import Membership, Organization, OrganizationDocument
from .serializers import (
    OrganizationDocumentSerializer,
    OrganizationMemberCreateSerializer,
    OrganizationMemberSerializer,
    OrganizationSerializer,
    OrganizationVerificationSerializer,
)


class OrganizationViewSet(viewsets.ModelViewSet):
    serializer_class = OrganizationSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ["organization_type", "status"]
    search_fields = ["name", "registration_number", "email"]
    ordering_fields = ["name", "created_at", "status"]

    def get_queryset(self):
        qs = Organization.objects.all().select_related("verified_by").annotate(
            member_count_ann=Count("memberships", distinct=True)
        )
        if is_platform_admin(self.request.user):
            return qs
        return qs.filter(id__in=user_org_ids(self.request.user))

    def perform_create(self, serializer):
        if not is_platform_admin(self.request.user):
            raise PermissionDenied("Only platform administrators can create organizations directly.")
        serializer.save()

    def perform_update(self, serializer):
        org = self.get_object()
        if not is_platform_admin(self.request.user) and self.request.user.role != User.Role.PROVIDER_ADMIN:
            raise PermissionDenied("Not allowed to update this organization.")
        serializer.save()

    def perform_destroy(self, instance):
        if not is_platform_admin(self.request.user):
            raise PermissionDenied("Only platform administrators can delete organizations.")
        log_action(self.request.user, "organization.deleted", instance, changes={"name": instance.name})
        instance.delete()

    @action(detail=True, methods=["post"], permission_classes=[IsPlatformAdmin])
    def verify(self, request, pk=None):
        org = self.get_object()
        serializer = OrganizationVerificationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        act = serializer.validated_data["action"]
        reason = serializer.validated_data.get("reason", "")
        old_status = org.status
        if act == "verify":
            org.verify(request.user)
            if org.organization_type == Organization.Type.INSURER:
                from apps.insurance.models import Insurer

                Insurer.objects.get_or_create(
                    organization=org,
                    defaults={"display_name": org.name, "license_number": org.registration_number},
                )
            for m in org.memberships.filter(is_active=True).select_related("user"):
                notify(m.user, "Organization verified", f"{org.name} has been verified.", "organization")
        elif act == "reject":
            org.status = Organization.Status.REJECTED
            org.rejection_reason = reason
            org.save(update_fields=["status", "rejection_reason"])
        elif act == "more_info":
            org.status = Organization.Status.MORE_INFO
            org.rejection_reason = reason
            org.save(update_fields=["status", "rejection_reason"])
        elif act == "suspend":
            org.status = Organization.Status.SUSPENDED
            org.save(update_fields=["status"])
        elif act == "reactivate":
            org.status = Organization.Status.VERIFIED
            org.verified_at = timezone.now()
            org.save(update_fields=["status", "verified_at"])
        from apps.organizations.models import OrganizationStatusHistory

        OrganizationStatusHistory.objects.create(
            organization=org, from_status=old_status, to_status=org.status,
            changed_by=request.user, notes=reason,
        )
        return Response(OrganizationSerializer(org).data)

    @action(detail=True, methods=["get", "post"], url_path="members")
    def members(self, request, pk=None):
        org = self.get_object()
        if request.method == "GET":
            qs = org.memberships.select_related("user")
            return Response(OrganizationMemberSerializer(qs, many=True).data)

        self._assert_can_manage_members(request, org)
        serializer = OrganizationMemberCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"]
        target = User.objects.filter(email__iexact=email).first()
        if not target:
            raise ValidationError({"email": "No registered user with this email. Ask them to register first."})
        if Membership.objects.filter(user=target, organization=org).exists():
            raise ValidationError({"email": "User is already a member of this organization."})
        role = serializer.validated_data["role"]
        membership = Membership.objects.create(user=target, organization=org, role=role, invited_by=request.user)
        role_map = {
            Membership.Role.AGENT: User.Role.AGENT,
            Membership.Role.INSPECTOR: User.Role.INSPECTOR,
            Membership.Role.CLAIMS: User.Role.CLAIMS_OFFICER,
            Membership.Role.ADMIN: User.Role.PROVIDER_ADMIN,
            Membership.Role.STAFF: User.Role.PROVIDER_STAFF,
        }
        if target.role == User.Role.CUSTOMER and role in role_map:
            target.role = role_map[role]
            target.save(update_fields=["role"])
        if role == Membership.Role.AGENT:
            AgentProfile.objects.get_or_create(user=target)
        if role == Membership.Role.INSPECTOR:
            InspectorProfile.objects.get_or_create(user=target)
        notify(target, "Organization membership", f"You were added to {org.name} as {role}.", "organization")
        return Response(OrganizationMemberSerializer(membership).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["patch", "delete"], url_path=r"members/(?P<member_id>[^/.]+)")
    def member_detail(self, request, pk=None, member_id=None):
        org = self.get_object()
        self._assert_can_manage_members(request, org)
        membership = get_object_or_404(Membership, pk=member_id, organization=org)
        if membership.role == Membership.Role.OWNER:
            raise ValidationError("The organization owner membership cannot be modified here.")
        if request.method == "DELETE":
            membership.is_active = False
            membership.save(update_fields=["is_active"])
            return Response(status=status.HTTP_204_NO_CONTENT)
        role = request.data.get("role")
        if role not in dict(Membership.Role.choices):
            raise ValidationError({"role": "Invalid role."})
        membership.role = role
        if "is_active" in request.data:
            membership.is_active = bool(request.data["is_active"])
        membership.save()
        return Response(OrganizationMemberSerializer(membership).data)

    @action(detail=True, methods=["get", "post"], url_path="documents")
    def documents(self, request, pk=None):
        org = self.get_object()
        if request.method == "GET":
            return Response(
                OrganizationDocumentSerializer(
                    org.documents.all(), many=True, context=self.get_serializer_context()
                ).data
            )
        serializer = OrganizationDocumentSerializer(data=request.data, context=self.get_serializer_context())
        serializer.is_valid(raise_exception=True)
        serializer.save(organization=org, uploaded_by=request.user)
        log_action(
            request.user,
            "organization.document_uploaded",
            org,
            changes={"document": str(serializer.instance.id)},
        )
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(
        detail=True,
        methods=["get"],
        url_path=r"documents/(?P<doc_id>[^/.]+)/download",
        url_name="document-download",
    )
    def download_document(self, request, pk=None, doc_id=None):
        org = self.get_object()
        doc = get_object_or_404(OrganizationDocument, pk=doc_id, organization=org)
        response = protected_file_response(doc.file)
        if response is None:
            return Response({"detail": "Document file is unavailable."}, status=404)
        log_action(
            request.user,
            "organization.document_downloaded",
            org,
            changes={"document": str(doc.id), "filename": doc.file.name},
        )
        return response

    def _assert_can_manage_members(self, request, org):
        if is_platform_admin(request.user):
            return
        if request.user.role not in {User.Role.PROVIDER_ADMIN}:
            raise PermissionDenied("Only organization administrators can manage members.")
        if not Membership.objects.filter(user=request.user, organization=org, is_active=True).exists():
            raise PermissionDenied("You are not a member of this organization.")


class MyOrganizationsView(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]

    def list(self, request):
        memberships = (
            Membership.objects.filter(user=request.user, is_active=True)
            .select_related("organization")
            .order_by("organization__name")
        )
        data = [
            {
                "membership_id": str(m.id),
                "role": m.role,
                "organization": OrganizationSerializer(m.organization).data,
            }
            for m in memberships
        ]
        return Response(data)
