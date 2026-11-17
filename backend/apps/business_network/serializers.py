from rest_framework import serializers

from apps.insurance.models import Insurer
from apps.organizations.models import Organization

from .models import (
    CustomerConsent,
    DealerBranch,
    DealerVehicle,
    DealerVehiclePhoto,
    Partnership,
    PartnershipActivity,
    PartnershipCommissionTerms,
    PartnershipRequest,
)


class DealerBranchSerializer(serializers.ModelSerializer):
    vehicle_count = serializers.SerializerMethodField()

    class Meta:
        model = DealerBranch
        fields = ("id", "dealership", "name", "address", "county", "phone", "is_active", "vehicle_count", "created_at")
        read_only_fields = ("id", "created_at")

    def get_vehicle_count(self, obj):
        return obj.vehicles.count()


class DealerVehiclePhotoSerializer(serializers.ModelSerializer):
    class Meta:
        model = DealerVehiclePhoto
        fields = ("id", "vehicle", "image", "is_primary", "order")
        read_only_fields = ("id",)


class DealerVehicleSerializer(serializers.ModelSerializer):
    photos = DealerVehiclePhotoSerializer(many=True, read_only=True)
    branch_name = serializers.CharField(source="branch.name", read_only=True)
    dealership_name = serializers.CharField(source="dealership.name", read_only=True)

    class Meta:
        model = DealerVehicle
        fields = (
            "id", "dealership", "dealership_name", "branch", "branch_name",
            "registration_number", "vin", "make", "model", "year", "category",
            "fuel_type", "transmission", "mileage", "condition", "asking_price",
            "description", "status", "sold_at", "photos", "created_at", "updated_at",
        )
        read_only_fields = ("id", "dealership_name", "branch_name", "sold_at", "created_at", "updated_at")

    def validate_year(self, value):
        from django.utils import timezone

        if value > timezone.now().year + 1:
            raise serializers.ValidationError("Year cannot be in the future.")
        return value


class PartnershipActivitySerializer(serializers.ModelSerializer):
    actor_name = serializers.CharField(source="actor.full_name", read_only=True)

    class Meta:
        model = PartnershipActivity
        fields = ("id", "partnership", "actor", "actor_name", "action", "notes", "created_at")
        read_only_fields = fields


class PartnershipCommissionTermsSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name", read_only=True)

    class Meta:
        model = PartnershipCommissionTerms
        fields = (
            "id", "partnership", "product", "product_name", "commission_type",
            "rate", "fixed_amount", "effective_date", "status", "created_at",
        )
        read_only_fields = ("id", "partnership", "product_name", "created_at")


class PartnershipSerializer(serializers.ModelSerializer):
    insurer_name = serializers.CharField(source="insurer.display_name", read_only=True)
    insurer_id = serializers.CharField(read_only=True)
    dealership_name = serializers.CharField(source="dealership.name", read_only=True)
    dealership_id = serializers.CharField(read_only=True)
    dealership_logo = serializers.ImageField(source="dealership.logo", read_only=True)
    activity = PartnershipActivitySerializer(many=True, read_only=True)
    commission_terms = PartnershipCommissionTermsSerializer(many=True, read_only=True)

    class Meta:
        model = Partnership
        fields = (
            "id", "insurer", "insurer_id", "insurer_name", "dealership", "dealership_id",
            "dealership_name", "dealership_logo", "status", "terms", "effective_date",
            "expiry_date", "approved_by", "approved_at", "rejection_reason",
            "suspension_reason", "activity", "commission_terms", "created_at", "updated_at",
        )
        read_only_fields = (
            "id", "insurer_name", "insurer_id", "dealership_name", "dealership_id",
            "dealership_logo", "status", "approved_by", "approved_at", "rejection_reason",
            "suspension_reason", "activity", "commission_terms", "created_at", "updated_at",
        )


class PartnershipRequestSerializer(serializers.ModelSerializer):
    from_name = serializers.CharField(source="from_organization.name", read_only=True)
    to_name = serializers.CharField(source="to_organization.name", read_only=True)
    from_type = serializers.CharField(source="from_organization.organization_type", read_only=True)
    to_type = serializers.CharField(source="to_organization.organization_type", read_only=True)

    class Meta:
        model = PartnershipRequest
        fields = (
            "id", "from_organization", "from_name", "from_type", "to_organization",
            "to_name", "to_type", "message", "status", "responded_by", "responded_at",
            "response_note", "partnership", "created_at",
        )
        read_only_fields = (
            "id", "from_name", "from_type", "to_name", "to_type", "status",
            "responded_by", "responded_at", "response_note", "partnership", "created_at",
        )


class CustomerConsentSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source="customer.full_name", read_only=True)
    dealership_name = serializers.CharField(source="dealership.name", read_only=True)
    insurer_name = serializers.CharField(source="insurer.display_name", read_only=True)

    class Meta:
        model = CustomerConsent
        fields = (
            "id", "customer", "customer_name", "dealership", "dealership_name",
            "insurer", "insurer_name", "data_categories", "consent_method",
            "status", "granted_at", "withdrawn_at", "created_at",
        )
        read_only_fields = (
            "id", "customer_name", "dealership_name", "insurer_name", "status",
            "granted_at", "withdrawn_at", "created_at",
        )


class InsurerDiscoverSerializer(serializers.ModelSerializer):
    organization_id = serializers.CharField(read_only=True)
    name = serializers.CharField(source="organization.name", read_only=True)
    trading_name = serializers.CharField(source="organization.trading_name", read_only=True)
    logo = serializers.ImageField(source="organization.logo", read_only=True)
    description = serializers.CharField(source="organization.description", read_only=True)
    county = serializers.CharField(source="organization.county", read_only=True)
    country = serializers.CharField(source="organization.country", read_only=True)
    status = serializers.CharField(source="organization.status", read_only=True)
    product_count = serializers.SerializerMethodField()
    categories = serializers.SerializerMethodField()
    partnership_status = serializers.SerializerMethodField()

    class Meta:
        model = Insurer
        fields = (
            "organization_id", "display_name", "name", "trading_name", "logo", "description",
            "county", "country", "status", "rating", "product_count", "categories",
            "partnership_status",
        )

    def get_product_count(self, obj):
        ann = getattr(obj, "product_count_ann", None)
        return ann if ann is not None else obj.products.count()

    def get_categories(self, obj):
        return list(obj.products.values_list("category", flat=True).distinct())

    def get_partnership_status(self, obj):
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return "none"
        org_ids = set()
        from apps.common.models import user_org_ids

        for oid in user_org_ids(request.user):
            org_ids.add(str(oid))
        from .models import Partnership

        p = Partnership.objects.filter(
            insurer=obj, dealership_id__in=org_ids
        ).exclude(status__in=[Partnership.Status.REJECTED, Partnership.Status.TERMINATED]).first()
        if p:
            return p.status
        return "none"


class DealershipDiscoverSerializer(serializers.ModelSerializer):
    branch_count = serializers.SerializerMethodField()
    inventory_count = serializers.SerializerMethodField()
    partnership_status = serializers.SerializerMethodField()

    class Meta:
        model = Organization
        fields = (
            "id", "name", "trading_name", "logo", "description", "county", "country",
            "status", "branch_count", "inventory_count", "partnership_status",
        )

    def get_branch_count(self, obj):
        return obj.branches.count()

    def get_inventory_count(self, obj):
        return obj.inventory.exclude(status=DealerVehicle.Status.SOLD).count()

    def get_partnership_status(self, obj):
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return "none"
        from apps.common.scoping import user_insurer_ids

        insurer_ids = user_insurer_ids(request.user)
        if not insurer_ids:
            return "none"
        from .models import Partnership

        p = Partnership.objects.filter(
            dealership=obj, insurer_id__in=insurer_ids
        ).exclude(status__in=[Partnership.Status.REJECTED, Partnership.Status.TERMINATED]).first()
        if p:
            return p.status
        return "none"


class PartnershipRequestCreateSerializer(serializers.Serializer):
    to_organization = serializers.UUIDField()
    message = serializers.CharField(required=False, allow_blank=True)


class PartnershipRequestRespondSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=["approve", "reject", "more_info"])
    note = serializers.CharField(required=False, allow_blank=True)


class PartnershipActionSerializer(serializers.Serializer):
    reason = serializers.CharField(required=False, allow_blank=True)


class ConsentCreateSerializer(serializers.Serializer):
    customer = serializers.UUIDField()
    insurer = serializers.UUIDField()
    data_categories = serializers.ListField(child=serializers.CharField(), required=False)
    consent_method = serializers.ChoiceField(choices=["in_person", "digital", "verbal"], required=False)


class DealerVehiclePhotoUploadSerializer(serializers.Serializer):
    image = serializers.ImageField()
    is_primary = serializers.BooleanField(required=False, default=False)
