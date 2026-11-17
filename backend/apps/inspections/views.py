from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.accounts.models import User
from apps.audit.services import log_action
from apps.common.files import protected_file_response
from apps.common.models import is_platform_admin, user_org_ids
from apps.common.utils import generate_reference
from apps.notifications.services import notify

from .models import ZONES, DamageRecord, Inspection
from .serializers import (
    CompleteInspectionSerializer,
    DamageRecordSerializer,
    InspectionSerializer,
    ScheduleInspectionSerializer,
)


class InspectionViewSet(viewsets.ModelViewSet):
    serializer_class = InspectionSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ["status", "inspection_type", "vehicle", "inspector"]
    search_fields = ["inspection_number", "vehicle__registration_number", "inspector__email"]
    ordering_fields = ["created_at", "scheduled_at", "status"]
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    http_method_names = ["get", "post", "head", "options"]

    def get_queryset(self):
        qs = Inspection.objects.select_related(
            "vehicle", "inspector", "requested_by", "organization", "application", "policy"
        ).prefetch_related("damages")
        user = self.request.user
        if is_platform_admin(user):
            return qs
        if user.role == User.Role.CUSTOMER:
            return qs.filter(Q(requested_by=user) | Q(vehicle__owner=user))
        if user.role == User.Role.INSPECTOR:
            return qs.filter(Q(inspector=user) | Q(organization_id__in=user_org_ids(user)))
        if user.role == User.Role.CLAIMS_OFFICER:
            return qs.filter(claim__officer=user) | qs.filter(organization_id__in=user_org_ids(user))
        return qs.filter(
            Q(organization_id__in=user_org_ids(user))
            | Q(application__quotation__insurer__organization_id__in=user_org_ids(user))
            | Q(policy__insurer__organization_id__in=user_org_ids(user))
        ).distinct()

    def perform_create(self, serializer):
        user = self.request.user
        if user.role not in {User.Role.CUSTOMER, User.Role.CLAIMS_OFFICER, User.Role.PROVIDER_ADMIN, User.Role.PROVIDER_STAFF, User.Role.ADMIN, User.Role.SUPER_ADMIN}:
            raise PermissionDenied("Not allowed to request inspections.")
        extra = {}
        if user.role == User.Role.CUSTOMER:
            extra = {"application": None, "policy": None, "claim": None}
        inspection = serializer.save(
            requested_by=user,
            inspection_number=generate_reference("INS", 10),
            **extra,
        )
        log_action(user, "inspection.requested", inspection)
        notify(
            user,
            "Inspection requested",
            f"Inspection {inspection.inspection_number} was created for {inspection.vehicle.registration_number}.",
            "inspection",
            f"/inspections/{inspection.id}",
        )

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        return Response(self.get_serializer(serializer.instance).data, status=201)

    @action(detail=False, methods=["get"], url_path="zones")
    def zones(self, request):
        return Response(ZONES)

    @action(detail=True, methods=["post"])
    def schedule(self, request, pk=None):
        inspection = self.get_object()
        self._require_staff(inspection, request.user)
        serializer = ScheduleInspectionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        inspector = User.objects.filter(pk=serializer.validated_data["inspector"], role=User.Role.INSPECTOR).first()
        if not inspector:
            raise ValidationError({"inspector": "Inspector not found."})
        inspection.inspector = inspector
        inspection.scheduled_at = serializer.validated_data["scheduled_at"]
        inspection.location = serializer.validated_data["location"]
        inspection.status = Inspection.Status.SCHEDULED
        update_fields = ["inspector", "scheduled_at", "location", "status"]
        if inspection.organization_id is None:
            org_ids = user_org_ids(request.user)
            if org_ids:
                inspection.organization_id = org_ids[0]
                update_fields.append("organization")
        inspection.save(update_fields=update_fields)
        notify(inspector, "New inspection assigned", f"{inspection.inspection_number} scheduled.", "inspection")
        notify(inspection.requested_by, "Inspection scheduled", f"{inspection.inspection_number} is scheduled.", "inspection")
        log_action(request.user, "inspection.scheduled", inspection)
        return Response(InspectionSerializer(inspection).data)

    @action(detail=True, methods=["post"])
    def start(self, request, pk=None):
        inspection = self.get_object()
        if inspection.inspector_id != request.user.id and not is_platform_admin(request.user):
            raise PermissionDenied("Only the assigned inspector can start this inspection.")
        if inspection.status != Inspection.Status.SCHEDULED:
            raise ValidationError("Only scheduled inspections can be started.")
        inspection.status = Inspection.Status.IN_PROGRESS
        inspection.save(update_fields=["status"])
        log_action(request.user, "inspection.started", inspection)
        return Response(InspectionSerializer(inspection).data)

    @action(detail=True, methods=["post"])
    def complete(self, request, pk=None):
        inspection = self.get_object()
        if inspection.inspector_id != request.user.id and not is_platform_admin(request.user):
            raise PermissionDenied("Only the assigned inspector can complete this inspection.")
        if inspection.status not in {Inspection.Status.IN_PROGRESS, Inspection.Status.SCHEDULED}:
            raise ValidationError("Inspection cannot be completed in its current state.")
        serializer = CompleteInspectionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        inspection.report_summary = serializer.validated_data["report_summary"]
        inspection.overall_condition = serializer.validated_data["overall_condition"]
        if serializer.validated_data.get("report_file"):
            inspection.report_file = serializer.validated_data["report_file"]
        inspection.status = Inspection.Status.COMPLETED
        inspection.completed_at = timezone.now()
        inspection.save()
        notify(inspection.requested_by, "Inspection completed", f"{inspection.inspection_number} report is ready.", "inspection")
        log_action(request.user, "inspection.completed", inspection)
        return Response(InspectionSerializer(inspection).data)

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        inspection = self.get_object()
        if not is_platform_admin(request.user) and inspection.requested_by_id != request.user.id:
            self._require_staff(inspection, request.user)
        if inspection.status == Inspection.Status.COMPLETED:
            raise ValidationError("Completed inspections cannot be cancelled.")
        inspection.status = Inspection.Status.CANCELLED
        inspection.save(update_fields=["status"])
        log_action(request.user, "inspection.cancelled", inspection)
        return Response(InspectionSerializer(inspection).data)

    @action(detail=True, methods=["get", "post"], url_path="damages", parser_classes=[MultiPartParser, FormParser, JSONParser])
    def damages(self, request, pk=None):
        inspection = self.get_object()
        if request.method == "GET":
            return Response(DamageRecordSerializer(inspection.damages.all(), many=True).data)
        if inspection.inspector_id != request.user.id and not is_platform_admin(request.user):
            raise PermissionDenied("Only the assigned inspector can record damage.")
        serializer = DamageRecordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        damage = serializer.save(inspection=inspection, created_by=request.user)
        log_action(request.user, "inspection.damage_recorded", inspection, changes={"zone": damage.zone, "severity": damage.severity})
        return Response(DamageRecordSerializer(damage).data, status=201)

    @action(
        detail=True,
        methods=["get"],
        url_path="report/download",
        url_name="report-download",
    )
    def download_report(self, request, pk=None):
        inspection = self.get_object()
        self._require_download(inspection, request.user)
        response = protected_file_response(inspection.report_file)
        if response is None:
            return Response({"detail": "Inspection report is unavailable."}, status=404)
        log_action(
            request.user,
            "inspection.report_downloaded",
            inspection,
            changes={"filename": inspection.report_file.name},
        )
        return response

    @action(
        detail=True,
        methods=["get"],
        url_path=r"damages/(?P<damage_id>[^/.]+)/photo",
        url_name="damage-photo-download",
    )
    def download_damage_photo(self, request, pk=None, damage_id=None):
        inspection = self.get_object()
        self._require_download(inspection, request.user)
        damage = get_object_or_404(DamageRecord, pk=damage_id, inspection=inspection)
        response = protected_file_response(damage.photo)
        if response is None:
            return Response({"detail": "Damage photo is unavailable."}, status=404)
        log_action(
            request.user,
            "inspection.damage_photo_downloaded",
            inspection,
            changes={"damage": str(damage.id), "filename": damage.photo.name},
        )
        return response

    @action(detail=True, methods=["delete"], url_path=r"damages/(?P<damage_id>[^/.]+)")
    def delete_damage(self, request, pk=None, damage_id=None):
        inspection = self.get_object()
        if inspection.inspector_id != request.user.id and not is_platform_admin(request.user):
            raise PermissionDenied("Not allowed.")
        damage = get_object_or_404(DamageRecord, pk=damage_id, inspection=inspection)
        damage.delete()
        return Response(status=204)

    @action(detail=True, methods=["post"], url_path="ai-assist", parser_classes=[MultiPartParser, FormParser])
    def ai_assist(self, request, pk=None):
        inspection = self.get_object()
        if inspection.inspector_id != request.user.id and not is_platform_admin(request.user):
            raise PermissionDenied("Only the assigned inspector can use AI assistance.")
        image = request.FILES.get("image")
        if not image:
            raise ValidationError({"image": "Upload an image for AI assistance."})
        from apps.ai_services.services import analyze_damage_image

        result = analyze_damage_image(image)
        return Response(result)

    def _require_staff(self, inspection, user):
        if is_platform_admin(user):
            return
        if inspection.organization_id and inspection.organization_id in user_org_ids(user):
            return
        if inspection.application_id and inspection.application.quotation.insurer.organization_id in user_org_ids(user):
            return
        if inspection.policy_id and inspection.policy.insurer.organization_id in user_org_ids(user):
            return
        if user.role == User.Role.CLAIMS_OFFICER and inspection.claim_id:
            return
        if inspection.organization_id is None and user.role in {
            User.Role.PROVIDER_ADMIN,
            User.Role.PROVIDER_STAFF,
            User.Role.CLAIMS_OFFICER,
        } and user_org_ids(user):
            return
        raise PermissionDenied("Not allowed to manage this inspection.")

    def _require_download(self, inspection, user):
        if is_platform_admin(user):
            return
        if user.role == User.Role.CUSTOMER:
            if inspection.requested_by_id == user.id or (
                inspection.vehicle_id and inspection.vehicle.owner_id == user.id
            ):
                return
            raise PermissionDenied("Not allowed to download this inspection.")
        if user.role == User.Role.INSPECTOR:
            if inspection.inspector_id == user.id:
                return
            if inspection.organization_id in user_org_ids(user):
                return
            raise PermissionDenied("Not allowed to download this inspection.")
        if user.role == User.Role.CLAIMS_OFFICER:
            if inspection.claim_id and inspection.claim.officer_id == user.id:
                return
            if inspection.organization_id in user_org_ids(user):
                return
            raise PermissionDenied("Not allowed to download this inspection.")
        # Provider / dealer / agent: must be linked to their organisation.
        if inspection.organization_id and inspection.organization_id in user_org_ids(user):
            return
        if inspection.application_id and inspection.application.quotation.insurer.organization_id in user_org_ids(user):
            return
        if inspection.policy_id and inspection.policy.insurer.organization_id in user_org_ids(user):
            return
        raise PermissionDenied("Not allowed to download this inspection.")
