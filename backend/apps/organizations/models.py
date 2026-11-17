import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.text import slugify

from apps.common.models import TimeStampedModel


class Organization(TimeStampedModel):
    class Type(models.TextChoices):
        INSURER = "insurer", "Insurance Provider"
        AGENCY = "agency", "Insurance Agency"
        INSPECTION = "inspection", "Inspection Company"
        DEALER = "dealer", "Motor Vehicle Dealership"
        PLATFORM = "platform", "Platform"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending Verification"
        MORE_INFO = "more_info", "More Information Required"
        VERIFIED = "verified", "Verified"
        SUSPENDED = "suspended", "Suspended"
        REJECTED = "rejected", "Rejected"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255, unique=True)
    trading_name = models.CharField(max_length=255, blank=True)
    slug = models.SlugField(max_length=280, unique=True, blank=True)
    organization_type = models.CharField(max_length=30, choices=Type.choices, default=Type.INSURER, db_index=True)
    registration_number = models.CharField(max_length=100, blank=True)
    tax_id = models.CharField(max_length=100, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=30, blank=True)
    website = models.URLField(blank=True)
    address = models.CharField(max_length=255, blank=True)
    country = models.CharField(max_length=100, blank=True, default="Kenya")
    county = models.CharField(max_length=100, blank=True)
    logo = models.ImageField(upload_to="organizations/logos/", null=True, blank=True)
    description = models.TextField(blank=True)
    representative_name = models.CharField(max_length=150, blank=True)
    representative_position = models.CharField(max_length=100, blank=True)
    representative_phone = models.CharField(max_length=30, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING, db_index=True)
    verified_at = models.DateTimeField(null=True, blank=True)
    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="verified_orgs"
    )
    rejection_reason = models.TextField(blank=True)

    class Meta:
        ordering = ["name"]

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.name)[:250] or "organization"
            slug = base
            n = 1
            while Organization.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                n += 1
                slug = f"{base}-{n}"
            self.slug = slug
        super().save(*args, **kwargs)

    def verify(self, by=None):
        self.status = self.Status.VERIFIED
        self.verified_at = timezone.now()
        self.verified_by = by
        self.save(update_fields=["status", "verified_at", "verified_by"])

    def __str__(self):
        return self.name


class Membership(TimeStampedModel):
    class Role(models.TextChoices):
        OWNER = "owner", "Owner"
        ADMIN = "admin", "Administrator"
        STAFF = "staff", "Staff"
        AGENT = "agent", "Agent"
        INSPECTOR = "inspector", "Inspector"
        CLAIMS = "claims", "Claims Officer"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="memberships")
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="memberships")
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.STAFF)
    is_active = models.BooleanField(default=True)
    invited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="invitations_sent"
    )

    class Meta:
        unique_together = ("user", "organization")
        ordering = ["organization__name"]

    def __str__(self):
        return f"{self.user.email} @ {self.organization.name}"


class OrganizationDocument(TimeStampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="documents")
    document_type = models.CharField(max_length=80)
    file = models.FileField(upload_to="organizations/documents/")
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    is_verified = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.organization.name} - {self.document_type}"


class OrganizationStatusHistory(TimeStampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="status_history")
    from_status = models.CharField(max_length=20, blank=True)
    to_status = models.CharField(max_length=20)
    changed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.organization.name}: {self.from_status} -> {self.to_status}"
