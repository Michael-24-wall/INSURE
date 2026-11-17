from django.db.models import Q
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.accounts.models import User
from apps.audit.services import log_action
from apps.common.files import protected_file_response
from apps.common.models import is_platform_admin, user_org_ids

from .models import Vehicle, VehicleDocument
from .serializers import VehicleDocumentSerializer, VehicleSerializer


class VehicleViewSet(viewsets.ModelViewSet):
    serializer_class = VehicleSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ["category", "fuel_type", "usage", "is_active"]
    search_fields = ["registration_number", "make", "model", "chassis_number"]
    ordering_fields = ["created_at", "estimated_value", "manufacturing_year"]

    def get_queryset(self):
        user = self.request.user
        qs = Vehicle.objects.alive().select_related("owner")
        if is_platform_admin(user):
            return qs
        if user.role == User.Role.CUSTOMER:
            return qs.filter(owner=user)
        # Providers/inspectors can see vehicles linked to their organization's work.
        org_ids = user_org_ids(user)
        return qs.filter(
            Q(insurance_applications__quotation__insurer__organization_id__in=org_ids)
            | Q(inspections__inspector=user)
            | Q(inspections__organization_id__in=org_ids)
        ).distinct()

    def perform_create(self, serializer):
        if self.request.user.role not in {User.Role.CUSTOMER, User.Role.ADMIN, User.Role.SUPER_ADMIN}:
            raise PermissionDenied("Only customers can register vehicles.")
        serializer.save(owner=self.request.user)

    def perform_update(self, serializer):
        instance = self.get_object()
        if not is_platform_admin(self.request.user) and instance.owner_id != self.request.user.id:
            raise PermissionDenied("Only the vehicle owner can update this vehicle.")
        serializer.save()

    def perform_destroy(self, instance):
        if not is_platform_admin(self.request.user) and instance.owner_id != self.request.user.id:
            raise PermissionDenied("You can only delete your own vehicles.")
        instance.delete()

    @action(detail=True, methods=["get", "post"], url_path="documents", parser_classes=[MultiPartParser, FormParser, JSONParser])
    def documents(self, request, pk=None):
        vehicle = self.get_object()
        if request.method == "GET":
            return Response(
                VehicleDocumentSerializer(
                    vehicle.documents.all(), many=True, context=self.get_serializer_context()
                ).data
            )
        serializer = VehicleDocumentSerializer(data=request.data, context=self.get_serializer_context())
        serializer.is_valid(raise_exception=True)
        serializer.save(vehicle=vehicle, uploaded_by=request.user)
        log_action(request.user, "vehicle.document_uploaded", vehicle, changes={"document": str(serializer.instance.id)})
        return Response(serializer.data, status=201)

    @action(
        detail=True,
        methods=["get"],
        url_path=r"documents/(?P<doc_id>[^/.]+)/download",
        url_name="document-download",
    )
    def download_document(self, request, pk=None, doc_id=None):
        vehicle = self.get_object()
        doc = vehicle.documents.filter(pk=doc_id).first()
        if not doc:
            return Response({"detail": "Document not found."}, status=404)
        response = protected_file_response(doc.file)
        if response is None:
            return Response({"detail": "Document file is unavailable."}, status=404)
        log_action(
            request.user,
            "vehicle.document_downloaded",
            vehicle,
            changes={"document": str(doc.id), "filename": doc.file.name},
        )
        return response

    @action(detail=True, methods=["delete"], url_path=r"documents/(?P<doc_id>[^/.]+)")
    def delete_document(self, request, pk=None, doc_id=None):
        vehicle = self.get_object()
        doc = vehicle.documents.filter(pk=doc_id).first()
        if not doc:
            return Response({"detail": "Document not found."}, status=404)
        if not is_platform_admin(request.user) and vehicle.owner_id != request.user.id:
            raise PermissionDenied("Not allowed.")
        doc.file.delete(save=False)
        doc.delete()
        return Response(status=204)
