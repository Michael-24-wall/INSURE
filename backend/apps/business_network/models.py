import uuid

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone

from apps.common.models import TimeStampedModel
from apps.organizations.models import Organization
from apps.vehicles.models import Vehicle


class DealerBranch(TimeStampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    dealership = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="branches",
        limit_choices_to={"organization_type": Organization.Type.DEALER},
    )
    name = models.CharField(max_length=200)
    address = models.CharField(max_length=255, blank=True)
    county = models.CharField(max_length=100, blank=True)
    phone = models.CharField(max_length=30, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "dealer branches"

    def __str__(self):
        return f"{self.dealership.name} - {self.name}"


class DealerVehicle(TimeStampedModel):
    class Status(models.TextChoices):
        AVAILABLE = "available", "Available"
        RESERVED = "reserved", "Reserved"
        SOLD = "sold", "Sold"
        UNAVAILABLE = "unavailable", "Unavailable"

    class Transmission(models.TextChoices):
        MANUAL = "manual", "Manual"
        AUTOMATIC = "automatic", "Automatic"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    dealership = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="inventory",
        limit_choices_to={"organization_type": Organization.Type.DEALER},
    )
    branch = models.ForeignKey(
        DealerBranch, null=True, blank=True, on_delete=models.SET_NULL, related_name="vehicles"
    )
    registration_number = models.CharField(max_length=20, blank=True)
    vin = models.CharField(max_length=100, blank=True)
    make = models.CharField(max_length=100)
    model = models.CharField(max_length=100)
    year = models.PositiveIntegerField()
    category = models.CharField(max_length=30, choices=Vehicle.Category.choices, default=Vehicle.Category.SALOON)
    fuel_type = models.CharField(max_length=20, choices=Vehicle.Fuel.choices, default=Vehicle.Fuel.PETROL)
    transmission = models.CharField(max_length=20, choices=Transmission.choices, default=Transmission.AUTOMATIC)
    mileage = models.PositiveIntegerField(null=True, blank=True)
    condition = models.CharField(max_length=20, choices=[("new", "New"), ("used", "Used")], default="used")
    asking_price = models.DecimalField(max_digits=14, decimal_places=2, default=0, validators=[MinValueValidator(0)])
    description = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.AVAILABLE, db_index=True)
    sold_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.make} {self.model} ({self.year})"


class DealerVehiclePhoto(TimeStampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    vehicle = models.ForeignKey(DealerVehicle, on_delete=models.CASCADE, related_name="photos")
    image = models.ImageField(upload_to="dealerships/vehicles/%Y/%m/")
    is_primary = models.BooleanField(default=False)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "-created_at"]

    def __str__(self):
        return f"Photo for {self.vehicle}"


class Partnership(TimeStampedModel):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        UNDER_REVIEW = "under_review", "Under Review"
        MORE_INFO = "more_info", "More Information Required"
        APPROVED = "approved", "Approved"
        ACTIVE = "active", "Active"
        REJECTED = "rejected", "Rejected"
        SUSPENDED = "suspended", "Suspended"
        TERMINATED = "terminated", "Terminated"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    insurer = models.ForeignKey(
        "insurance.Insurer", on_delete=models.CASCADE, related_name="partnerships"
    )
    dealership = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="insurer_partnerships",
        limit_choices_to={"organization_type": Organization.Type.DEALER},
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING, db_index=True)
    terms = models.TextField(blank=True)
    effective_date = models.DateField(null=True, blank=True)
    expiry_date = models.DateField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="initiated_partnerships",
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="approved_partnerships",
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True)
    suspension_reason = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["insurer", "dealership"],
                condition=models.Q(status__in=["pending", "under_review", "more_info", "approved", "active"]),
                name="unique_active_partnership",
            )
        ]

    def __str__(self):
        return f"{self.insurer.display_name} <> {self.dealership.name}"

    @property
    def is_active(self):
        return self.status == self.Status.ACTIVE


class PartnershipRequest(TimeStampedModel):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        UNDER_REVIEW = "under_review", "Under Review"
        MORE_INFO = "more_info", "More Information Required"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"
        CANCELLED = "cancelled", "Cancelled"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    from_organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="sent_partnership_requests"
    )
    to_organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="received_partnership_requests"
    )
    message = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING, db_index=True)
    responded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="responded_partnership_requests",
    )
    responded_at = models.DateTimeField(null=True, blank=True)
    response_note = models.TextField(blank=True)
    partnership = models.ForeignKey(
        Partnership, null=True, blank=True, on_delete=models.SET_NULL, related_name="request"
    )

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.from_organization.name} -> {self.to_organization.name}"


class PartnershipActivity(TimeStampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    partnership = models.ForeignKey(Partnership, on_delete=models.CASCADE, related_name="activity")
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    action = models.CharField(max_length=80)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.partnership} - {self.action}"


class CustomerConsent(TimeStampedModel):
    class Status(models.TextChoices):
        GRANTED = "granted", "Granted"
        WITHDRAWN = "withdrawn", "Withdrawn"

    class Method(models.TextChoices):
        IN_PERSON = "in_person", "In Person"
        DIGITAL = "digital", "Digital"
        VERBAL = "verbal", "Verbal"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    customer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="consents")
    dealership = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="customer_consents",
        limit_choices_to={"organization_type": Organization.Type.DEALER},
    )
    insurer = models.ForeignKey("insurance.Insurer", on_delete=models.CASCADE, related_name="customer_consents")
    data_categories = models.JSONField(default=list, blank=True)
    consent_method = models.CharField(max_length=20, choices=Method.choices, default=Method.DIGITAL)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.GRANTED)
    granted_at = models.DateTimeField(auto_now_add=True)
    withdrawn_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.customer.email} -> {self.insurer.display_name}"


class PartnershipCommissionTerms(TimeStampedModel):
    class Type(models.TextChoices):
        FIXED = "fixed", "Fixed Amount"
        PERCENTAGE = "percentage", "Percentage of Premium"

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        ACTIVE = "active", "Active"
        INACTIVE = "inactive", "Inactive"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    partnership = models.ForeignKey(Partnership, on_delete=models.CASCADE, related_name="commission_terms")
    product = models.ForeignKey(
        "insurance.Product", null=True, blank=True, on_delete=models.SET_NULL, related_name="commission_terms"
    )
    commission_type = models.CharField(max_length=20, choices=Type.choices, default=Type.PERCENTAGE)
    rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    fixed_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    effective_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)

    class Meta:
        ordering = ["-created_at"]
        verbose_name_plural = "partnership commission terms"

    def __str__(self):
        return f"{self.partnership} - {self.get_commission_type_display()}"
