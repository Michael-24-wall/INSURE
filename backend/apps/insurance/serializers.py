from decimal import Decimal

from django.utils import timezone
from rest_framework import serializers

from apps.accounts.models import User
from apps.common.utils import generate_reference
from apps.vehicles.models import Vehicle

from .models import Application, CoverageOption, Insurer, Policy, Product, Quotation, QuotationRequest


class InsurerSerializer(serializers.ModelSerializer):
    organization_name = serializers.CharField(source="organization.name", read_only=True)
    organization_status = serializers.CharField(source="organization.status", read_only=True)
    product_count = serializers.SerializerMethodField()

    def get_product_count(self, obj):
        count = getattr(obj, "product_count_ann", None)
        return count if count is not None else obj.products.count()

    class Meta:
        model = Insurer
        fields = (
            "id", "organization", "organization_name", "organization_status", "display_name",
            "license_number", "description", "rating", "claims_payout_ratio", "is_active",
            "product_count", "created_at",
        )
        read_only_fields = ("id", "created_at", "product_count")


class CoverageOptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = CoverageOption
        fields = ("id", "product", "name", "description", "premium_rate", "limit_amount", "is_default")
        read_only_fields = ("id",)


class ProductSerializer(serializers.ModelSerializer):
    insurer_name = serializers.CharField(source="insurer.display_name", read_only=True)
    organization_id = serializers.CharField(source="insurer.organization_id", read_only=True)
    coverage_options = CoverageOptionSerializer(many=True, read_only=True)

    class Meta:
        model = Product
        fields = (
            "id", "insurer", "insurer_name", "organization_id", "name", "code", "category",
            "description", "base_premium_rate", "minimum_premium", "excess_amount",
            "min_vehicle_value", "max_vehicle_value", "min_vehicle_year", "benefits",
            "exclusions", "terms", "is_active", "version", "coverage_options",
            "created_at", "updated_at",
        )
        read_only_fields = ("id", "version", "created_at", "updated_at", "coverage_options")

    def validate(self, attrs):
        if "min_vehicle_value" in attrs:
            min_v = attrs["min_vehicle_value"]
        elif self.instance is not None:
            min_v = self.instance.min_vehicle_value
        else:
            min_v = Decimal("0.00")
        if "max_vehicle_value" in attrs:
            max_v = attrs["max_vehicle_value"]
        elif self.instance is not None:
            max_v = self.instance.max_vehicle_value
        else:
            max_v = Decimal("100000000.00")
        if min_v is not None and max_v is not None and min_v >= max_v:
            raise serializers.ValidationError("Maximum vehicle value must exceed the minimum.")
        rate = attrs.get("base_premium_rate")
        if rate is not None and rate <= 0:
            raise serializers.ValidationError({"base_premium_rate": "Premium rate must be positive."})
        return attrs


class QuotationRequestSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source="customer.full_name", read_only=True)
    customer_email = serializers.EmailField(source="customer.email", read_only=True)
    dealership_name = serializers.CharField(source="dealership.name", read_only=True)
    insurer_name = serializers.CharField(source="insurer.display_name", read_only=True)
    vehicle_summary = serializers.SerializerMethodField()
    quotation_count = serializers.SerializerMethodField()
    lowest_premium = serializers.SerializerMethodField()
    is_expired = serializers.BooleanField(read_only=True)

    def get_quotation_count(self, obj):
        count = getattr(obj, "quotation_count_ann", None)
        return count if count is not None else obj.quotations.count()

    class Meta:
        model = QuotationRequest
        fields = (
            "id", "request_number", "customer", "customer_name", "customer_email", "vehicle",
            "vehicle_summary", "product", "insurer", "insurer_name", "coverage_type", "sum_insured",
            "desired_start_date", "notes", "status", "insurer_notes", "clarification_note",
            "clarification_requested_at", "reviewed_by", "reviewed_at", "expires_at", "is_expired",
            "quotation_count", "lowest_premium", "dealership", "dealership_name", "dealership_branch",
            "partnership", "consent", "created_at", "updated_at",
        )
        read_only_fields = (
            "id", "request_number", "customer", "status", "insurer", "insurer_notes",
            "clarification_note", "clarification_requested_at", "reviewed_by", "reviewed_at",
            "expires_at", "is_expired", "created_at", "updated_at", "vehicle_summary",
            "quotation_count", "lowest_premium", "dealership", "dealership_branch", "partnership",
            "consent",
        )

    def get_vehicle_summary(self, obj):
        v = obj.vehicle
        return {
            "id": str(v.id),
            "registration_number": v.registration_number,
            "make": v.make,
            "model": v.model,
            "year": v.manufacturing_year,
            "value": str(v.estimated_value),
        }

    def get_lowest_premium(self, obj):
        ann = getattr(obj, "lowest_premium_ann", None)
        if ann is not None:
            return str(ann)
        q = obj.quotations.order_by("premium").first()
        return str(q.premium) if q else None

    def validate_vehicle(self, vehicle):
        request = self.context.get("request")
        if request and request.user.role == User.Role.CUSTOMER and vehicle.owner_id != request.user.id:
            raise serializers.ValidationError("You can only request quotations for your own vehicles.")
        return vehicle

    def validate_sum_insured(self, value):
        if value <= 0:
            raise serializers.ValidationError("Sum insured must be greater than zero.")
        return value

    def validate_desired_start_date(self, value):
        if value < timezone.now().date():
            raise serializers.ValidationError("Start date cannot be in the past.")
        return value


class QuotationSerializer(serializers.ModelSerializer):
    insurer_name = serializers.CharField(source="insurer.display_name", read_only=True)
    product_name = serializers.CharField(source="product.name", read_only=True)
    product_category = serializers.CharField(source="product.category", read_only=True)
    request_number = serializers.CharField(source="request.request_number", read_only=True)
    vehicle_summary = serializers.SerializerMethodField()
    coverage_options = CoverageOptionSerializer(source="product.coverage_options", many=True, read_only=True)
    application_id = serializers.SerializerMethodField()
    total_payable = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)

    class Meta:
        model = Quotation
        fields = (
            "id", "quotation_number", "request", "request_number", "insurer", "insurer_name",
            "product", "product_name", "product_category", "coverage_options", "sum_insured",
            "premium", "taxes", "fees", "other_charges", "total_payable", "excess_amount",
            "benefits", "exclusions", "coverage_limits", "deductibles", "terms", "valid_until",
            "status", "source", "provider_reference", "notes", "vehicle_summary", "application_id", "created_at",
        )
        read_only_fields = (
            "id", "quotation_number", "request", "product", "insurer", "insurer_name", "product_name",
            "product_category", "request_number", "status", "source", "created_at", "vehicle_summary",
            "coverage_options", "application_id", "total_payable",
        )

    def get_vehicle_summary(self, obj):
        v = obj.request.vehicle
        return {
            "registration_number": v.registration_number,
            "make": v.make,
            "model": v.model,
            "year": v.manufacturing_year,
        }

    def get_application_id(self, obj):
        application = getattr(obj, "application", None)
        return str(application.id) if application else None


class QuotationCreateSerializer(serializers.Serializer):
    request = serializers.PrimaryKeyRelatedField(queryset=QuotationRequest.objects.all())
    product = serializers.PrimaryKeyRelatedField(queryset=Product.objects.alive())
    premium = serializers.DecimalField(max_digits=14, decimal_places=2, min_value=Decimal("0.01"))
    taxes = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal("0"), required=False, default=Decimal("0.00"))
    fees = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal("0"), required=False, default=Decimal("0.00"))
    other_charges = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal("0"), required=False, default=Decimal("0.00"))
    excess_amount = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal("0"))
    benefits = serializers.ListField(child=serializers.CharField(), required=False)
    exclusions = serializers.ListField(child=serializers.CharField(), required=False)
    coverage_limits = serializers.DictField(required=False)
    deductibles = serializers.DictField(required=False)
    terms = serializers.CharField(required=False, allow_blank=True)
    notes = serializers.CharField(required=False, allow_blank=True)
    valid_days = serializers.IntegerField(default=14, min_value=1, max_value=90)
    expires_at = serializers.DateTimeField(required=False)

    def validate_expires_at(self, value):
        if value <= timezone.now():
            raise serializers.ValidationError("The quotation expiry must be in the future.")
        return value


class ApplicationSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source="customer.full_name", read_only=True)
    customer_email = serializers.EmailField(source="customer.email", read_only=True)
    insurer_name = serializers.CharField(source="quotation.insurer.display_name", read_only=True)
    insurer_id = serializers.CharField(source="quotation.insurer_id", read_only=True)
    product_name = serializers.CharField(source="quotation.product.name", read_only=True)
    quotation_number = serializers.CharField(source="quotation.quotation_number", read_only=True)
    premium = serializers.DecimalField(source="quotation.premium", max_digits=14, decimal_places=2, read_only=True)
    sum_insured = serializers.DecimalField(source="quotation.sum_insured", max_digits=14, decimal_places=2, read_only=True)
    vehicle_summary = serializers.SerializerMethodField()
    policy_id = serializers.SerializerMethodField()

    class Meta:
        model = Application
        fields = (
            "id", "application_number", "customer", "customer_name", "customer_email",
            "quotation", "quotation_number", "insurer_name", "insurer_id", "product_name",
            "premium", "sum_insured", "vehicle", "vehicle_summary", "status", "submitted_at",
            "reviewed_by", "reviewed_at", "review_notes", "provider_reference", "policy_id",
            "created_at", "updated_at",
        )
        read_only_fields = (
            "id", "application_number", "customer", "vehicle", "status", "submitted_at",
            "reviewed_by", "reviewed_at", "review_notes", "provider_reference", "created_at", "updated_at",
            "vehicle_summary",
        )

    def get_vehicle_summary(self, obj):
        v = obj.vehicle
        return {
            "id": str(v.id),
            "registration_number": v.registration_number,
            "make": v.make,
            "model": v.model,
            "year": v.manufacturing_year,
        }

    def get_policy_id(self, obj):
        policy = Policy.objects.filter(application=obj).first()
        return str(policy.id) if policy else None

    def validate_quotation(self, quotation):
        request = self.context.get("request")
        if request and quotation.request.customer_id != request.user.id:
            raise serializers.ValidationError("This quotation does not belong to you.")
        if quotation.status not in {Quotation.Status.SELECTED, Quotation.Status.RECEIVED}:
            raise serializers.ValidationError("This quotation is not available for an application.")
        if quotation.valid_until < timezone.now():
            raise serializers.ValidationError("This quotation has expired.")
        qreq = quotation.request
        if qreq.is_expired:
            raise serializers.ValidationError("The quotation request has expired.")
        if qreq.status in {
            QuotationRequest.Status.EXPIRED,
            QuotationRequest.Status.CANCELLED,
            QuotationRequest.Status.REJECTED,
        }:
            raise serializers.ValidationError("This quotation request is no longer active.")
        if qreq.consent_id and qreq.consent.status == "withdrawn":
            raise serializers.ValidationError("Customer consent for data sharing has been withdrawn.")
        if Application.objects.filter(quotation=quotation).exists():
            raise serializers.ValidationError("An application already exists for this quotation.")
        return quotation

    def create(self, validated_data):
        quotation = validated_data["quotation"]
        request = self.context["request"]
        qreq = quotation.request
        application = Application.objects.create(
            application_number=generate_reference("APP", 10),
            customer=request.user,
            quotation=quotation,
            vehicle=qreq.vehicle,
            dealership=qreq.dealership,
            dealership_branch=qreq.dealership_branch,
            partnership=qreq.partnership,
        )
        qreq.status = QuotationRequest.Status.CONVERTED
        qreq.save(update_fields=["status"])
        return application

    def to_representation(self, instance):
        data = super().to_representation(instance)
        request = self.context.get("request")
        if request and request.user.role in {User.Role.DEALER_ADMIN, User.Role.DEALER_STAFF}:
            for field in ("customer_email", "review_notes", "reviewed_by", "reviewed_at"):
                data.pop(field, None)
        return data


class AgentApplicationCreateSerializer(serializers.Serializer):
    quotation = serializers.PrimaryKeyRelatedField(queryset=Quotation.objects.all())
    customer = serializers.PrimaryKeyRelatedField(queryset=User.objects.filter(role=User.Role.CUSTOMER))
    agent = serializers.PrimaryKeyRelatedField(queryset=User.objects.filter(role=User.Role.AGENT), required=False)

    def validate(self, attrs):
        quotation = attrs["quotation"]
        customer = attrs["customer"]
        if quotation.request.customer_id != customer.id:
            raise serializers.ValidationError({"quotation": "This quotation does not belong to the selected customer."})
        if quotation.status not in {Quotation.Status.SELECTED, Quotation.Status.RECEIVED}:
            raise serializers.ValidationError({"quotation": "This quotation is not available for an application."})
        if quotation.valid_until < timezone.now():
            raise serializers.ValidationError({"quotation": "This quotation has expired."})
        if quotation.request.is_expired:
            raise serializers.ValidationError({"quotation": "The quotation request has expired."})
        if quotation.request.consent_id and quotation.request.consent.status == "withdrawn":
            raise serializers.ValidationError({"quotation": "Customer consent for data sharing has been withdrawn."})
        if Application.objects.filter(quotation=quotation).exists():
            raise serializers.ValidationError({"quotation": "An application already exists for this quotation."})
        return attrs


class DealerApplicationCreateSerializer(serializers.Serializer):
    quotation = serializers.PrimaryKeyRelatedField(queryset=Quotation.objects.all())

    def validate_quotation(self, quotation):
        if quotation.status not in {Quotation.Status.SELECTED, Quotation.Status.RECEIVED}:
            raise serializers.ValidationError("This quotation is not available for an application.")
        if quotation.valid_until < timezone.now():
            raise serializers.ValidationError("This quotation has expired.")
        if quotation.request.is_expired:
            raise serializers.ValidationError("The quotation request has expired.")
        if quotation.request.status == QuotationRequest.Status.CONVERTED:
            raise serializers.ValidationError("This request was already converted into an application.")
        if quotation.request.consent_id and quotation.request.consent.status == "withdrawn":
            raise serializers.ValidationError("Customer consent for data sharing has been withdrawn.")
        if Application.objects.filter(quotation=quotation).exists():
            raise serializers.ValidationError("An application already exists for this quotation.")
        return quotation


class PolicySerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source="customer.full_name", read_only=True)
    customer_email = serializers.EmailField(source="customer.email", read_only=True)
    insurer_name = serializers.CharField(source="insurer.display_name", read_only=True)
    insurer_id = serializers.CharField(read_only=True)
    product_name = serializers.CharField(source="product.name", read_only=True)
    vehicle_summary = serializers.SerializerMethodField()
    days_to_expiry = serializers.SerializerMethodField()
    claim_count = serializers.SerializerMethodField()
    certificate = serializers.SerializerMethodField()

    def get_certificate(self, obj):
        if not obj.certificate:
            return None
        from django.urls import reverse

        request = self.context.get("request")
        try:
            path = reverse("policies-document", kwargs={"pk": obj.pk})
        except Exception:
            path = f"/api/v1/policies/{obj.pk}/document/"
        return request.build_absolute_uri(path) if request else path

    def get_claim_count(self, obj):
        count = getattr(obj, "claim_count_ann", None)
        return count if count is not None else obj.claims.count()

    class Meta:
        model = Policy
        fields = (
            "id", "policy_number", "application", "customer", "customer_name", "customer_email",
            "insurer", "insurer_name", "insurer_id", "product", "product_name", "vehicle",
            "vehicle_summary", "start_date", "end_date", "premium", "sum_insured",
            "excess_amount", "status", "issued_at", "provider_reference", "certificate",
            "days_to_expiry", "claim_count", "created_at",
        )
        read_only_fields = fields

    def get_vehicle_summary(self, obj):
        v = obj.vehicle
        return {
            "id": str(v.id),
            "registration_number": v.registration_number,
            "make": v.make,
            "model": v.model,
            "year": v.manufacturing_year,
        }

    def get_days_to_expiry(self, obj):
        return (obj.end_date - timezone.now().date()).days


class PolicyIssueSerializer(serializers.Serializer):
    start_date = serializers.DateField(required=False)
    end_date = serializers.DateField(required=False)
    provider_reference = serializers.CharField(required=False, allow_blank=True)

    def validate(self, attrs):
        start = attrs.get("start_date")
        end = attrs.get("end_date")
        if start and end and end <= start:
            raise serializers.ValidationError("End date must be after start date.")
        return attrs
