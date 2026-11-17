from django.contrib.auth.password_validation import validate_password
from django.db import transaction
from django.utils import timezone
from rest_framework import serializers

from apps.organizations.models import Membership, Organization

from .models import (
    AgentProfile,
    CustomerProfile,
    EmailVerificationToken,
    InspectorProfile,
    User,
)


class UserPublicSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(read_only=True)
    kyc_status = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ("id", "email", "first_name", "last_name", "full_name", "phone", "role", "email_verified", "kyc_status", "is_active", "created_at")
        read_only_fields = fields

    def get_kyc_status(self, obj):
        profile = getattr(obj, "customer_profile", None)
        return profile.kyc_status if profile else None


class CustomerProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomerProfile
        fields = (
            "national_id", "date_of_birth", "address", "city", "county",
            "kyc_status", "kyc_submitted_at", "kyc_notes",
        )
        read_only_fields = ("kyc_status", "kyc_submitted_at", "kyc_notes")


class CustomerKycSubmitSerializer(serializers.Serializer):
    national_id = serializers.CharField(max_length=50, required=False, allow_blank=True)
    date_of_birth = serializers.DateField(required=False, allow_null=True)
    address = serializers.CharField(max_length=255, required=False, allow_blank=True)
    city = serializers.CharField(max_length=100, required=False, allow_blank=True)
    county = serializers.CharField(max_length=100, required=False, allow_blank=True)


class CustomerKycReviewSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=["approve", "reject"])
    notes = serializers.CharField(required=False, allow_blank=True)


class AgentProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = AgentProfile
        fields = ("license_number", "commission_rate", "region", "is_verified")
        read_only_fields = ("commission_rate", "is_verified")


class InspectorProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = InspectorProfile
        fields = ("certification_number", "region", "is_verified", "capacity_per_day")
        read_only_fields = ("is_verified",)


class MeSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(read_only=True)
    customer_profile = CustomerProfileSerializer(read_only=True)
    agent_profile = AgentProfileSerializer(read_only=True)
    inspector_profile = InspectorProfileSerializer(read_only=True)
    memberships = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            "id", "email", "first_name", "last_name", "full_name", "phone", "role",
            "email_verified", "totp_enabled", "is_active", "created_at",
            "customer_profile", "agent_profile", "inspector_profile", "memberships",
        )
        read_only_fields = ("id", "email", "role", "email_verified", "totp_enabled", "is_active", "created_at")

    def get_memberships(self, obj):
        return [
            {
                "organization_id": str(m.organization_id),
                "organization_name": m.organization.name,
                "organization_type": m.organization.organization_type,
                "role": m.role,
                "is_active": m.is_active,
            }
            for m in Membership.objects.filter(user=obj, is_active=True).select_related("organization")
        ]


class CustomerRegisterSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)
    first_name = serializers.CharField(max_length=150)
    last_name = serializers.CharField(max_length=150)
    phone = serializers.CharField(max_length=30, required=False, allow_blank=True)

    def validate_email(self, value):
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("An account with this email already exists.")
        return value.lower()

    def validate_password(self, value):
        validate_password(value)
        return value

    @transaction.atomic
    def create(self, validated_data):
        password = validated_data.pop("password")
        user = User.objects.create_user(password=password, role=User.Role.CUSTOMER, **validated_data)
        CustomerProfile.objects.create(user=user)
        token = EmailVerificationToken.objects.create(
            user=user, expires_at=timezone.now() + timezone.timedelta(days=3)
        )
        return user, token


class ProviderRegisterSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)
    first_name = serializers.CharField(max_length=150)
    last_name = serializers.CharField(max_length=150)
    phone = serializers.CharField(max_length=30, required=False, allow_blank=True)
    organization_name = serializers.CharField(max_length=255)
    trading_name = serializers.CharField(max_length=255, required=False, allow_blank=True)
    registration_number = serializers.CharField(max_length=100, required=False, allow_blank=True)
    tax_id = serializers.CharField(max_length=100, required=False, allow_blank=True)
    organization_email = serializers.EmailField(required=False, allow_blank=True)
    organization_phone = serializers.CharField(max_length=30, required=False, allow_blank=True)
    website = serializers.URLField(required=False, allow_blank=True)
    address = serializers.CharField(max_length=255, required=False, allow_blank=True)
    country = serializers.CharField(max_length=100, required=False, allow_blank=True)
    county = serializers.CharField(max_length=100, required=False, allow_blank=True)
    position = serializers.CharField(max_length=100, required=False, allow_blank=True)

    def validate_email(self, value):
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("An account with this email already exists.")
        return value.lower()

    def validate_organization_name(self, value):
        if Organization.objects.filter(name__iexact=value).exists():
            raise serializers.ValidationError("An organization with this name already exists.")
        return value

    def validate_password(self, value):
        validate_password(value)
        return value

    @transaction.atomic
    def create(self, validated_data):
        password = validated_data.pop("password")
        org_name = validated_data.pop("organization_name")
        trading_name = validated_data.pop("trading_name", "")
        reg_no = validated_data.pop("registration_number", "")
        tax_id = validated_data.pop("tax_id", "")
        org_email = validated_data.pop("organization_email", "")
        org_phone = validated_data.pop("organization_phone", "")
        website = validated_data.pop("website", "")
        address = validated_data.pop("address", "")
        country = validated_data.pop("country", "") or "Kenya"
        county = validated_data.pop("county", "")
        position = validated_data.pop("position", "")
        user = User.objects.create_user(password=password, role=User.Role.PROVIDER_ADMIN, **validated_data)
        org = Organization.objects.create(
            name=org_name,
            trading_name=trading_name,
            organization_type=Organization.Type.INSURER,
            registration_number=reg_no,
            tax_id=tax_id,
            email=org_email or validated_data["email"],
            phone=org_phone,
            website=website,
            address=address,
            country=country,
            county=county,
            representative_name=f"{user.first_name} {user.last_name}".strip(),
            representative_position=position,
            representative_phone=user.phone,
            status=Organization.Status.PENDING,
        )
        Membership.objects.create(user=user, organization=org, role=Membership.Role.OWNER)
        token = EmailVerificationToken.objects.create(
            user=user, expires_at=timezone.now() + timezone.timedelta(days=3)
        )
        return user, org, token


class DealerRegisterSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)
    first_name = serializers.CharField(max_length=150)
    last_name = serializers.CharField(max_length=150)
    phone = serializers.CharField(max_length=30, required=False, allow_blank=True)
    position = serializers.CharField(max_length=100, required=False, allow_blank=True)
    organization_name = serializers.CharField(max_length=255)
    trading_name = serializers.CharField(max_length=255, required=False, allow_blank=True)
    registration_number = serializers.CharField(max_length=100, required=False, allow_blank=True)
    tax_id = serializers.CharField(max_length=100, required=False, allow_blank=True)
    organization_email = serializers.EmailField(required=False, allow_blank=True)
    organization_phone = serializers.CharField(max_length=30, required=False, allow_blank=True)
    website = serializers.URLField(required=False, allow_blank=True)
    address = serializers.CharField(max_length=255, required=False, allow_blank=True)
    country = serializers.CharField(max_length=100, required=False, allow_blank=True)
    county = serializers.CharField(max_length=100, required=False, allow_blank=True)
    description = serializers.CharField(required=False, allow_blank=True)

    def validate_email(self, value):
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("An account with this email already exists.")
        return value.lower()

    def validate_organization_name(self, value):
        if Organization.objects.filter(name__iexact=value).exists():
            raise serializers.ValidationError("An organization with this name already exists.")
        return value

    def validate_password(self, value):
        validate_password(value)
        return value

    @transaction.atomic
    def create(self, validated_data):
        password = validated_data.pop("password")
        position = validated_data.pop("position", "")
        org_name = validated_data.pop("organization_name")
        trading_name = validated_data.pop("trading_name", "")
        tax_id = validated_data.pop("tax_id", "")
        org_email = validated_data.pop("organization_email", "")
        org_phone = validated_data.pop("organization_phone", "")
        website = validated_data.pop("website", "")
        address = validated_data.pop("address", "")
        country = validated_data.pop("country", "") or "Kenya"
        county = validated_data.pop("county", "")
        description = validated_data.pop("description", "")
        reg_no = validated_data.pop("registration_number", "")

        user = User.objects.create_user(password=password, role=User.Role.DEALER_ADMIN, **validated_data)
        org = Organization.objects.create(
            name=org_name,
            trading_name=trading_name,
            organization_type=Organization.Type.DEALER,
            registration_number=reg_no,
            tax_id=tax_id,
            email=org_email or validated_data["email"],
            phone=org_phone,
            website=website,
            address=address,
            country=country,
            county=county,
            description=description,
            representative_name=f"{user.first_name} {user.last_name}".strip(),
            representative_position=position,
            representative_phone=user.phone,
            status=Organization.Status.PENDING,
        )
        Membership.objects.create(user=user, organization=org, role=Membership.Role.OWNER)
        token = EmailVerificationToken.objects.create(
            user=user, expires_at=timezone.now() + timezone.timedelta(days=3)
        )
        return user, org, token


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)


class PasswordChangeSerializer(serializers.Serializer):
    current_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True)

    def validate_new_password(self, value):
        validate_password(value)
        return value


class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()


class PasswordResetConfirmSerializer(serializers.Serializer):
    token = serializers.UUIDField()
    new_password = serializers.CharField(write_only=True)

    def validate_new_password(self, value):
        validate_password(value)
        return value


class EmailVerifySerializer(serializers.Serializer):
    token = serializers.UUIDField()


class TotpCodeSerializer(serializers.Serializer):
    code = serializers.CharField()


class TotpDisableSerializer(serializers.Serializer):
    password = serializers.CharField(write_only=True)


class TotpVerifySerializer(serializers.Serializer):
    challenge = serializers.CharField()
    code = serializers.CharField()


class AdminUserUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("first_name", "last_name", "phone", "role", "is_active", "email_verified")
