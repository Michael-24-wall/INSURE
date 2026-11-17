import os

from django.urls import reverse
from rest_framework import serializers

from apps.common.fields import ValidatedFileField

from .models import Vehicle, VehicleDocument


class VehicleDocumentSerializer(serializers.ModelSerializer):
    file = ValidatedFileField(write_only=True)
    download_url = serializers.SerializerMethodField()
    filename = serializers.SerializerMethodField()

    class Meta:
        model = VehicleDocument
        fields = (
            "id", "vehicle", "document_type", "file", "download_url", "filename",
            "uploaded_by", "is_verified", "extracted_data", "notes", "created_at",
        )
        read_only_fields = (
            "id", "vehicle", "uploaded_by", "is_verified", "extracted_data",
            "download_url", "filename", "created_at",
        )

    def get_download_url(self, obj):
        if not obj.file:
            return None
        path = reverse("vehicles-document-download", kwargs={"pk": obj.vehicle_id, "doc_id": obj.pk})
        request = self.context.get("request")
        return request.build_absolute_uri(path) if request else path

    def get_filename(self, obj):
        return os.path.basename(obj.file.name) if obj.file else None


class VehicleSerializer(serializers.ModelSerializer):
    documents = VehicleDocumentSerializer(many=True, read_only=True)

    class Meta:
        model = Vehicle
        fields = (
            "id", "owner", "registration_number", "make", "model", "manufacturing_year",
            "chassis_number", "engine_cc", "category", "fuel_type", "usage",
            "estimated_value", "color", "seat_capacity", "is_active", "documents",
            "created_at", "updated_at",
        )
        read_only_fields = ("id", "owner", "created_at", "updated_at")

    def validate_registration_number(self, value):
        normalized = value.upper().strip().replace(" ", "")
        request = self.context.get("request")
        owner = self.instance.owner if self.instance else (request.user if request else None)
        if owner is not None:
            qs = Vehicle.objects.alive().filter(owner=owner, registration_number=normalized)
            if self.instance is not None:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise serializers.ValidationError("You already have a vehicle with this registration number.")
        return normalized

    def validate_manufacturing_year(self, value):
        from django.utils import timezone

        if value > timezone.now().year + 1:
            raise serializers.ValidationError("Manufacturing year cannot be in the future.")
        return value

    def validate_estimated_value(self, value):
        if value < 0:
            raise serializers.ValidationError("Estimated value cannot be negative.")
        return value
