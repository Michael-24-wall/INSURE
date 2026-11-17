import os

from django.urls import reverse
from rest_framework import serializers

from apps.accounts.models import User
from apps.common.fields import ValidatedFileField

from .models import Membership, Organization, OrganizationDocument


class OrganizationSerializer(serializers.ModelSerializer):
    member_count = serializers.SerializerMethodField()
    verified_by_name = serializers.CharField(source="verified_by.full_name", read_only=True)

    def get_member_count(self, obj):
        count = getattr(obj, "member_count_ann", None)
        return count if count is not None else obj.memberships.count()

    class Meta:
        model = Organization
        fields = (
            "id", "name", "slug", "organization_type", "registration_number", "email", "phone",
            "website", "address", "description", "status", "verified_at", "verified_by_name",
            "rejection_reason", "member_count", "created_at", "updated_at",
        )
        read_only_fields = ("id", "slug", "status", "verified_at", "verified_by_name", "rejection_reason", "created_at", "updated_at")


class OrganizationMemberSerializer(serializers.ModelSerializer):
    user_email = serializers.EmailField(source="user.email", read_only=True)
    user_name = serializers.CharField(source="user.full_name", read_only=True)
    user_role = serializers.CharField(source="user.role", read_only=True)

    class Meta:
        model = Membership
        fields = ("id", "user", "user_email", "user_name", "user_role", "role", "is_active", "created_at")
        read_only_fields = ("id", "user_email", "user_name", "user_role", "created_at")


class OrganizationMemberCreateSerializer(serializers.Serializer):
    email = serializers.EmailField()
    role = serializers.ChoiceField(choices=Membership.Role.choices)

    def validate_email(self, value):
        return value.lower()


class OrganizationDocumentSerializer(serializers.ModelSerializer):
    file = ValidatedFileField(write_only=True)
    download_url = serializers.SerializerMethodField()
    filename = serializers.SerializerMethodField()

    class Meta:
        model = OrganizationDocument
        fields = (
            "id", "organization", "document_type", "file", "download_url", "filename",
            "uploaded_by", "is_verified", "created_at",
        )
        read_only_fields = (
            "id", "organization", "uploaded_by", "is_verified", "download_url", "filename", "created_at",
        )

    def get_download_url(self, obj):
        if not obj.file:
            return None
        path = reverse(
            "organizations-document-download",
            kwargs={"pk": obj.organization_id, "doc_id": obj.pk},
        )
        request = self.context.get("request")
        return request.build_absolute_uri(path) if request else path

    def get_filename(self, obj):
        return os.path.basename(obj.file.name) if obj.file else None


class OrganizationVerificationSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=["verify", "reject", "suspend", "reactivate", "more_info"])
    reason = serializers.CharField(required=False, allow_blank=True)
