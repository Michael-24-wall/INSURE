import uuid
from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone

from apps.common.models import SoftDeleteModel, TimeStampedModel
from apps.organizations.models import Organization


class Insurer(TimeStampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.OneToOneField(Organization, on_delete=models.CASCADE, related_name="insurer_profile")
    display_name = models.CharField(max_length=255)
    license_number = models.CharField(max_length=100, blank=True)
    license_expiry_date = models.DateField(null=True, blank=True)
    description = models.TextField(blank=True)
    rating = models.DecimalField(max_digits=3, decimal_places=2, default=Decimal("4.00"))
    claims_payout_ratio = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("0.00"))
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["display_name"]

    def __str__(self):
        return self.display_name

    @property
    def is_verified(self):
        return self.organization.status == Organization.Status.VERIFIED


class Product(TimeStampedModel, SoftDeleteModel):
    class Category(models.TextChoices):
        COMPREHENSIVE = "comprehensive", "Comprehensive"
        THIRD_PARTY = "third_party", "Third Party Only"
        THIRD_PARTY_FIRE_THEFT = "third_party_fire_theft", "Third Party, Fire & Theft"
        COMMERCIAL = "commercial", "Commercial Motor"
        MOTORCYCLE = "motorcycle", "Motorcycle"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    insurer = models.ForeignKey(Insurer, on_delete=models.CASCADE, related_name="products")
    name = models.CharField(max_length=200)
    code = models.CharField(max_length=60)
    category = models.CharField(max_length=40, choices=Category.choices, db_index=True)
    description = models.TextField(blank=True)
    base_premium_rate = models.DecimalField(
        max_digits=7, decimal_places=4, default=Decimal("5.0000"),
        help_text="Percentage of sum insured used as base premium.",
    )
    minimum_premium = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("5000.00"))
    excess_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("10000.00"))
    min_vehicle_value = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    max_vehicle_value = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("100000000.00"))
    min_vehicle_year = models.PositiveIntegerField(default=1990)
    benefits = models.JSONField(default=list, blank=True)
    exclusions = models.JSONField(default=list, blank=True)
    terms = models.TextField(blank=True)
    is_active = models.BooleanField(default=True, db_index=True)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ["insurer__display_name", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["insurer", "code"],
                condition=models.Q(deleted_at__isnull=True),
                name="unique_active_product_code_per_insurer",
            )
        ]

    def __str__(self):
        return f"{self.insurer.display_name} - {self.name}"

    def supports_vehicle(self, vehicle, sum_insured=None):
        value = sum_insured or vehicle.estimated_value
        return (
            self.is_active
            and self.min_vehicle_value <= value <= self.max_vehicle_value
            and vehicle.manufacturing_year >= self.min_vehicle_year
        )


class CoverageOption(TimeStampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="coverage_options")
    name = models.CharField(max_length=150)
    description = models.CharField(max_length=255, blank=True)
    premium_rate = models.DecimalField(max_digits=7, decimal_places=4, default=Decimal("0.0000"))
    limit_amount = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    is_default = models.BooleanField(default=False)

    class Meta:
        ordering = ["product", "name"]

    def __str__(self):
        return f"{self.product.name} - {self.name}"


class QuotationRequest(TimeStampedModel):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        UNDER_REVIEW = "under_review", "Under Review"
        MORE_INFO = "more_info", "More Information Required"
        QUOTED = "quoted", "Quotes Received"
        SELECTED = "selected", "Quotation Selected"
        CONVERTED = "converted", "Converted to Application"
        REJECTED = "rejected", "Rejected"
        EXPIRED = "expired", "Expired"
        CANCELLED = "cancelled", "Cancelled"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    request_number = models.CharField(max_length=30, unique=True, db_index=True)
    customer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="quotation_requests")
    vehicle = models.ForeignKey("vehicles.Vehicle", on_delete=models.CASCADE, related_name="quotation_requests")
    product = models.ForeignKey(Product, null=True, blank=True, on_delete=models.SET_NULL, related_name="quotation_requests")
    insurer = models.ForeignKey(
        Insurer, null=True, blank=True, on_delete=models.SET_NULL, related_name="directed_quotation_requests",
        help_text="Target insurer for dealer-originated requests. Blank means open marketplace.",
    )
    coverage_type = models.CharField(max_length=40, choices=Product.Category.choices)
    sum_insured = models.DecimalField(max_digits=14, decimal_places=2, validators=[MinValueValidator(Decimal("1"))])
    desired_start_date = models.DateField()
    notes = models.TextField(blank=True)
    dealership = models.ForeignKey(
        "organizations.Organization", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="dealer_quotation_requests",
    )
    dealership_branch = models.ForeignKey(
        "business_network.DealerBranch", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="quotation_requests",
    )
    partnership = models.ForeignKey(
        "business_network.Partnership", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="quotation_requests",
    )
    consent = models.ForeignKey(
        "business_network.CustomerConsent", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="quotation_requests",
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING, db_index=True)
    insurer_notes = models.TextField(blank=True)
    clarification_note = models.TextField(blank=True)
    clarification_requested_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="reviewed_quotation_requests",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.request_number

    @property
    def is_expired(self):
        return self.expires_at <= timezone.now()


class Quotation(TimeStampedModel):
    class Status(models.TextChoices):
        RECEIVED = "received", "Received"
        MORE_INFO = "more_info", "More Information Required"
        SELECTED = "selected", "Selected"
        REJECTED = "rejected", "Rejected"
        EXPIRED = "expired", "Expired"

    class Source(models.TextChoices):
        INTERNAL = "internal", "Platform Engine (insurer published rates)"
        PROVIDER_API = "provider_api", "Provider API"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    quotation_number = models.CharField(max_length=30, unique=True, db_index=True)
    request = models.ForeignKey(QuotationRequest, on_delete=models.CASCADE, related_name="quotations")
    insurer = models.ForeignKey(Insurer, on_delete=models.CASCADE, related_name="quotations")
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="quotations")
    sum_insured = models.DecimalField(max_digits=14, decimal_places=2)
    premium = models.DecimalField(max_digits=14, decimal_places=2)
    taxes = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    fees = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    other_charges = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    excess_amount = models.DecimalField(max_digits=12, decimal_places=2)
    benefits = models.JSONField(default=list, blank=True)
    exclusions = models.JSONField(default=list, blank=True)
    coverage_limits = models.JSONField(default=dict, blank=True)
    deductibles = models.JSONField(default=dict, blank=True)
    terms = models.TextField(blank=True)
    valid_until = models.DateTimeField()
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.RECEIVED, db_index=True)
    source = models.CharField(max_length=20, choices=Source.choices, default=Source.INTERNAL)
    provider_reference = models.CharField(max_length=120, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["premium"]
        constraints = [
            models.UniqueConstraint(fields=["request", "insurer", "product"], name="unique_quote_per_product")
        ]

    def __str__(self):
        return self.quotation_number

    @property
    def total_payable(self):
        return self.premium + self.taxes + self.fees + self.other_charges


class Application(TimeStampedModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        SUBMITTED = "submitted", "Submitted"
        UNDER_REVIEW = "under_review", "Under Review"
        MORE_INFO = "more_info", "Additional Information Required"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"
        WITHDRAWN = "withdrawn", "Withdrawn"
        POLICY_ISSUED = "policy_issued", "Policy Issued"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    application_number = models.CharField(max_length=30, unique=True, db_index=True)
    customer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="insurance_applications")
    quotation = models.OneToOneField(Quotation, on_delete=models.PROTECT, related_name="application")
    vehicle = models.ForeignKey("vehicles.Vehicle", on_delete=models.PROTECT, related_name="insurance_applications")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT, db_index=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    agent = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="agent_applications"
    )
    dealership = models.ForeignKey(
        "organizations.Organization", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="dealer_applications",
    )
    dealership_branch = models.ForeignKey(
        "business_network.DealerBranch", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="applications",
    )
    partnership = models.ForeignKey(
        "business_network.Partnership", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="applications",
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="reviewed_applications"
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_notes = models.TextField(blank=True)
    provider_reference = models.CharField(max_length=120, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.application_number

    @property
    def insurer(self):
        return self.quotation.insurer


class Policy(TimeStampedModel):
    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        EXPIRED = "expired", "Expired"
        CANCELLED = "cancelled", "Cancelled"
        LAPSED = "lapsed", "Lapsed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    policy_number = models.CharField(max_length=40, unique=True, db_index=True)
    application = models.OneToOneField(Application, on_delete=models.PROTECT, related_name="policy")
    customer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="policies")
    insurer = models.ForeignKey(Insurer, on_delete=models.PROTECT, related_name="policies")
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="policies")
    vehicle = models.ForeignKey("vehicles.Vehicle", on_delete=models.PROTECT, related_name="policies")
    start_date = models.DateField()
    end_date = models.DateField()
    premium = models.DecimalField(max_digits=14, decimal_places=2)
    sum_insured = models.DecimalField(max_digits=14, decimal_places=2)
    excess_amount = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE, db_index=True)
    issued_at = models.DateTimeField(default=timezone.now)
    provider_reference = models.CharField(max_length=120, blank=True)
    certificate = models.FileField(upload_to="policies/certificates/", null=True, blank=True)
    renewal_reminder_sent_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.policy_number

    @property
    def is_active(self):
        today = timezone.now().date()
        return self.status == self.Status.ACTIVE and self.start_date <= today <= self.end_date
