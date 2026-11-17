import hashlib
import os

from django.urls import reverse
from rest_framework import serializers

from apps.common.fields import ValidatedFileField

from .models import Claim, ClaimDocument, ClaimStatusHistory


class ClaimDocumentSerializer(serializers.ModelSerializer):
    file = ValidatedFileField(write_only=True)
    uploaded_by_name = serializers.CharField(source="uploaded_by.full_name", read_only=True)
    download_url = serializers.SerializerMethodField()
    filename = serializers.SerializerMethodField()

    class Meta:
        model = ClaimDocument
        fields = (
            "id", "claim", "document_type", "file", "download_url", "filename",
            "uploaded_by", "uploaded_by_name", "is_verified", "ai_classification",
            "ai_confidence", "notes", "checksum", "created_at",
        )
        read_only_fields = (
            "id", "claim", "uploaded_by", "uploaded_by_name", "is_verified",
            "ai_classification", "ai_confidence", "checksum", "download_url", "filename", "created_at",
        )

    def get_download_url(self, obj):
        if not obj.file:
            return None
        path = reverse("claims-document-download", kwargs={"pk": obj.claim_id, "doc_id": obj.pk})
        request = self.context.get("request")
        return request.build_absolute_uri(path) if request else path

    def get_filename(self, obj):
        return os.path.basename(obj.file.name) if obj.file else None

    def create(self, validated_data):
        f = validated_data.get("file")
        if f:
            digest = hashlib.sha256()
            for chunk in f.chunks():
                digest.update(chunk)
            validated_data["checksum"] = digest.hexdigest()
            try:
                f.seek(0)
            except Exception:
                pass
        return super().create(validated_data)


class ClaimStatusHistorySerializer(serializers.ModelSerializer):
    changed_by_name = serializers.CharField(source="changed_by.full_name", read_only=True)

    class Meta:
        model = ClaimStatusHistory
        fields = ("id", "from_status", "to_status", "changed_by", "changed_by_name", "notes", "created_at")
        read_only_fields = fields


class ClaimSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source="customer.full_name", read_only=True)
    customer_email = serializers.EmailField(source="customer.email", read_only=True)
    policy_number = serializers.CharField(source="policy.policy_number", read_only=True)
    insurer_name = serializers.CharField(source="policy.insurer.display_name", read_only=True)
    insurer_id = serializers.CharField(source="policy.insurer_id", read_only=True)
    vehicle_summary = serializers.SerializerMethodField()
    officer_name = serializers.CharField(source="officer.full_name", read_only=True)
    documents = ClaimDocumentSerializer(many=True, read_only=True)
    status_history = ClaimStatusHistorySerializer(many=True, read_only=True)
    inspection_ids = serializers.SerializerMethodField()

    class Meta:
        model = Claim
        fields = (
            "id", "claim_number", "policy", "policy_number", "insurer_name", "insurer_id",
            "customer", "customer_name", "customer_email", "claim_type", "incident_date",
            "incident_time", "location", "description", "police_report_number", "amount_claimed",
            "status", "officer", "officer_name", "decision_notes", "approved_amount",
            "settled_amount", "settlement_reference", "settled_at", "closed_at",
            "vehicle_summary", "documents", "status_history", "inspection_ids", "created_at", "updated_at",
        )
        read_only_fields = (
            "id", "claim_number", "customer", "customer_name", "customer_email", "status",
            "officer", "officer_name", "decision_notes", "approved_amount", "settled_amount",
            "settlement_reference", "settled_at", "closed_at", "status_history", "created_at", "updated_at",
        )

    def get_vehicle_summary(self, obj):
        v = obj.policy.vehicle
        return {
            "id": str(v.id),
            "registration_number": v.registration_number,
            "make": v.make,
            "model": v.model,
        }

    def get_inspection_ids(self, obj):
        return [str(i.id) for i in obj.inspections.all()] if obj.pk else []


class ClaimCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Claim
        fields = (
            "policy", "claim_type", "incident_date", "incident_time", "location",
            "description", "police_report_number", "amount_claimed",
        )

    def validate_policy(self, policy):
        request = self.context["request"]
        if request.user.role == "customer" and policy.customer_id != request.user.id:
            raise serializers.ValidationError("You can only claim against your own policy.")
        return policy

    def validate(self, attrs):
        policy = attrs["policy"]
        incident = attrs["incident_date"]
        if incident < policy.start_date or incident > policy.end_date:
            raise serializers.ValidationError(
                {"incident_date": "Incident date is outside the policy coverage period."}
            )
        if attrs["amount_claimed"] <= 0:
            raise serializers.ValidationError({"amount_claimed": "Claim amount must be greater than zero."})
        if attrs["amount_claimed"] > policy.sum_insured:
            raise serializers.ValidationError({"amount_claimed": "Claim amount cannot exceed the sum insured."})
        return attrs


class AssignOfficerSerializer(serializers.Serializer):
    officer = serializers.UUIDField()


class ClaimInfoSerializer(serializers.Serializer):
    notes = serializers.CharField()


class ClaimDecisionSerializer(serializers.Serializer):
    approved_amount = serializers.DecimalField(max_digits=14, decimal_places=2, required=False)
    notes = serializers.CharField(required=False, allow_blank=True)


class ClaimRejectSerializer(serializers.Serializer):
    notes = serializers.CharField()


class ClaimSettleSerializer(serializers.Serializer):
    settled_amount = serializers.DecimalField(max_digits=14, decimal_places=2)
    settlement_reference = serializers.CharField()


class ClaimInspectionSerializer(serializers.Serializer):
    inspector = serializers.UUIDField()
    scheduled_at = serializers.DateTimeField()
    location = serializers.CharField(max_length=255)
