import os

from django.urls import reverse
from django.utils import timezone
from rest_framework import serializers

from apps.common.fields import IMAGE_EXTENSIONS, ValidatedFileField

from .models import DamageRecord, Inspection


class DamageRecordSerializer(serializers.ModelSerializer):
    photo = ValidatedFileField(allowed_extensions=IMAGE_EXTENSIONS, required=False, write_only=True)
    photo_download_url = serializers.SerializerMethodField()
    photo_filename = serializers.SerializerMethodField()

    class Meta:
        model = DamageRecord
        fields = (
            "id", "inspection", "zone", "severity", "description", "photo",
            "photo_download_url", "photo_filename", "estimated_repair_cost",
            "ai_assisted", "ai_confidence", "created_by", "created_at",
        )
        read_only_fields = (
            "id", "inspection", "ai_assisted", "ai_confidence", "created_by",
            "photo_download_url", "photo_filename", "created_at",
        )

    def get_photo_download_url(self, obj):
        if not obj.photo:
            return None
        path = reverse(
            "inspections-damage-photo-download",
            kwargs={"pk": obj.inspection_id, "damage_id": obj.pk},
        )
        request = self.context.get("request")
        return request.build_absolute_uri(path) if request else path

    def get_photo_filename(self, obj):
        return os.path.basename(obj.photo.name) if obj.photo else None

    def validate_zone(self, value):
        from .models import ZONE_KEYS

        if value not in ZONE_KEYS:
            raise serializers.ValidationError("Unknown inspection zone.")
        return value

    def validate_estimated_repair_cost(self, value):
        if value < 0:
            raise serializers.ValidationError("Repair cost cannot be negative.")
        return value


class InspectionSerializer(serializers.ModelSerializer):
    vehicle_summary = serializers.SerializerMethodField()
    inspector_name = serializers.CharField(source="inspector.full_name", read_only=True)
    organization_name = serializers.CharField(source="organization.name", read_only=True)
    requested_by_name = serializers.CharField(source="requested_by.full_name", read_only=True)
    damages = DamageRecordSerializer(many=True, read_only=True)
    damage_count = serializers.IntegerField(source="damages.count", read_only=True)
    report_file = ValidatedFileField(required=False, write_only=True)
    report_download_url = serializers.SerializerMethodField()
    report_filename = serializers.SerializerMethodField()

    class Meta:
        model = Inspection
        fields = (
            "id", "inspection_number", "organization", "organization_name", "inspector",
            "inspector_name", "requested_by", "requested_by_name", "vehicle", "vehicle_summary",
            "application", "policy", "claim", "inspection_type", "status", "scheduled_at",
            "completed_at", "location", "notes", "report_summary", "report_file",
            "report_download_url", "report_filename", "overall_condition", "damages",
            "damage_count", "created_at", "updated_at",
        )
        read_only_fields = (
            "id", "inspection_number", "requested_by", "status", "completed_at", "created_at",
            "updated_at", "vehicle_summary", "inspector_name", "organization_name",
            "requested_by_name", "damages", "damage_count", "report_download_url", "report_filename",
        )

    def get_report_download_url(self, obj):
        if not obj.report_file:
            return None
        path = reverse("inspections-report-download", kwargs={"pk": obj.pk})
        request = self.context.get("request")
        return request.build_absolute_uri(path) if request else path

    def get_report_filename(self, obj):
        return os.path.basename(obj.report_file.name) if obj.report_file else None

    def get_vehicle_summary(self, obj):
        v = obj.vehicle
        return {
            "id": str(v.id),
            "registration_number": v.registration_number,
            "make": v.make,
            "model": v.model,
            "year": v.manufacturing_year,
        }

    def validate_vehicle(self, vehicle):
        request = self.context.get("request")
        if request and request.user.role == "customer" and vehicle.owner_id != request.user.id:
            raise serializers.ValidationError("You can only request inspections for your own vehicles.")
        return vehicle


class ScheduleInspectionSerializer(serializers.Serializer):
    inspector = serializers.UUIDField()
    scheduled_at = serializers.DateTimeField()
    location = serializers.CharField(max_length=255)

    def validate_scheduled_at(self, value):
        if value < timezone.now():
            raise serializers.ValidationError("Scheduled time cannot be in the past.")
        return value


class CompleteInspectionSerializer(serializers.Serializer):
    report_summary = serializers.CharField()
    overall_condition = serializers.ChoiceField(choices=["excellent", "good", "fair", "poor"])
    report_file = ValidatedFileField(required=False)
