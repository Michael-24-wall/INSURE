import uuid

from django.conf import settings
from django.db import models

from apps.common.models import TimeStampedModel


class Claim(TimeStampedModel):
    class Type(models.TextChoices):
        ACCIDENT = "accident", "Accident"
        THEFT = "theft", "Theft"
        FIRE = "fire", "Fire"
        THIRD_PARTY = "third_party", "Third Party Liability"
        WINDSHIELD = "windshield", "Windshield"
        OTHER = "other", "Other"

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        SUBMITTED = "submitted", "Submitted"
        UNDER_REVIEW = "under_review", "Under Review"
        INFO_REQUIRED = "info_required", "Additional Information Required"
        INSPECTION_SCHEDULED = "inspection_scheduled", "Inspection Scheduled"
        ASSESSMENT = "assessment", "Under Assessment"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"
        SETTLED = "settled", "Settled"
        CLOSED = "closed", "Closed"
        WITHDRAWN = "withdrawn", "Withdrawn"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    claim_number = models.CharField(max_length=30, unique=True, db_index=True)
    policy = models.ForeignKey("insurance.Policy", on_delete=models.PROTECT, related_name="claims")
    customer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="claims")
    claim_type = models.CharField(max_length=30, choices=Type.choices)
    incident_date = models.DateField()
    incident_time = models.TimeField(null=True, blank=True)
    location = models.CharField(max_length=255)
    description = models.TextField()
    police_report_number = models.CharField(max_length=100, blank=True)
    amount_claimed = models.DecimalField(max_digits=14, decimal_places=2)
    status = models.CharField(max_length=30, choices=Status.choices, default=Status.SUBMITTED, db_index=True)
    officer = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="assigned_claims"
    )
    decision_notes = models.TextField(blank=True)
    approved_amount = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    settled_amount = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    settlement_reference = models.CharField(max_length=120, blank=True)
    settled_at = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.claim_number

    @property
    def insurer(self):
        return self.policy.insurer


class ClaimDocument(TimeStampedModel):
    class DocType(models.TextChoices):
        POLICE_REPORT = "police_report", "Police Report"
        PHOTO = "photo", "Photograph"
        ESTIMATE = "estimate", "Repair Estimate"
        INVOICE = "invoice", "Invoice"
        ID = "id", "Identification"
        MEDICAL = "medical", "Medical Report"
        OTHER = "other", "Other"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    claim = models.ForeignKey(Claim, on_delete=models.CASCADE, related_name="documents")
    document_type = models.CharField(max_length=40, choices=DocType.choices, default=DocType.OTHER)
    file = models.FileField(upload_to="claims/documents/%Y/%m/")
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    is_verified = models.BooleanField(default=False)
    ai_classification = models.CharField(max_length=100, blank=True)
    ai_confidence = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    notes = models.CharField(max_length=255, blank=True)
    checksum = models.CharField(max_length=64, blank=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.claim.claim_number} - {self.document_type}"


class ClaimStatusHistory(TimeStampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    claim = models.ForeignKey(Claim, on_delete=models.CASCADE, related_name="status_history")
    from_status = models.CharField(max_length=30, blank=True)
    to_status = models.CharField(max_length=30)
    changed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.claim.claim_number}: {self.from_status} -> {self.to_status}"
