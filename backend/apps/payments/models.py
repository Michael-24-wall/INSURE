import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.common.models import TimeStampedModel
from apps.common.utils import generate_reference


def default_payment_reference():
    return generate_reference("PAY", 10)


class Payment(TimeStampedModel):
    class Purpose(models.TextChoices):
        PREMIUM = "premium", "Insurance Premium"
        CLAIM_EXCESS = "claim_excess", "Claim Excess"
        INSPECTION_FEE = "inspection_fee", "Inspection Fee"
        OTHER = "other", "Other"

    class Method(models.TextChoices):
        MPESA = "mpesa", "M-Pesa"
        CARD = "card", "Card"
        BANK = "bank", "Bank Transfer"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        PROCESSING = "processing", "Processing"
        SUCCEEDED = "succeeded", "Succeeded"
        SETTLED = "settled", "Settled"
        FAILED = "failed", "Failed"
        CANCELLED = "cancelled", "Cancelled"
        REFUNDED = "refunded", "Refunded"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    reference = models.CharField(max_length=40, unique=True, db_index=True, default=default_payment_reference)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="payments")
    purpose = models.CharField(max_length=30, choices=Purpose.choices, default=Purpose.PREMIUM, db_index=True)
    application = models.ForeignKey(
        "insurance.Application", null=True, blank=True, on_delete=models.SET_NULL, related_name="payments"
    )
    policy = models.ForeignKey(
        "insurance.Policy", null=True, blank=True, on_delete=models.SET_NULL, related_name="payments"
    )
    claim = models.ForeignKey("claims.Claim", null=True, blank=True, on_delete=models.SET_NULL, related_name="payments")
    inspection = models.ForeignKey(
        "inspections.Inspection", null=True, blank=True, on_delete=models.SET_NULL, related_name="payments"
    )
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    currency = models.CharField(max_length=3, default="KES")
    method = models.CharField(max_length=20, choices=Method.choices)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING, db_index=True)
    provider = models.CharField(max_length=40, blank=True)
    provider_reference = models.CharField(max_length=120, blank=True, db_index=True)
    checkout_request_id = models.CharField(max_length=120, blank=True, db_index=True)
    merchant_reference = models.CharField(max_length=120, blank=True)
    phone = models.CharField(max_length=30, blank=True)
    idempotency_key = models.CharField(max_length=120, unique=True, null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    failure_reason = models.CharField(max_length=255, blank=True)
    verified_at = models.DateTimeField(null=True, blank=True)
    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="verified_payments"
    )
    settled_at = models.DateTimeField(null=True, blank=True)
    receipt_number = models.CharField(max_length=40, blank=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.reference

    @property
    def is_final(self):
        return self.status in {self.Status.SUCCEEDED, self.Status.FAILED, self.Status.CANCELLED, self.Status.REFUNDED}


class Transaction(models.Model):
    class Type(models.TextChoices):
        CHARGE = "charge", "Charge"
        REFUND = "refund", "Refund"
        ADJUSTMENT = "adjustment", "Adjustment"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        SUCCEEDED = "succeeded", "Succeeded"
        FAILED = "failed", "Failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    payment = models.ForeignKey(Payment, on_delete=models.CASCADE, related_name="transactions")
    type = models.CharField(max_length=20, choices=Type.choices, default=Type.CHARGE)
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.SUCCEEDED)
    reference = models.CharField(max_length=120, blank=True, db_index=True)
    raw_response = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.type} {self.amount} - {self.payment.reference}"


class Refund(TimeStampedModel):
    class Status(models.TextChoices):
        REQUESTED = "requested", "Requested"
        PROCESSING = "processing", "Processing"
        COMPLETED = "completed", "Completed"
        REJECTED = "rejected", "Rejected"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    payment = models.ForeignKey(Payment, on_delete=models.PROTECT, related_name="refunds")
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    reason = models.TextField()
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.REQUESTED)
    reference = models.CharField(max_length=120, blank=True)
    processed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Refund {self.amount} for {self.payment.reference}"


class Commission(TimeStampedModel):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        APPROVED = "approved", "Approved"
        PAYABLE = "payable", "Payable"
        PAID = "paid", "Paid"
        REVERSED = "reversed", "Reversed"
        DISPUTED = "disputed", "Disputed"
        CANCELLED = "cancelled", "Cancelled"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    policy = models.ForeignKey("insurance.Policy", on_delete=models.CASCADE, related_name="commissions")
    agent = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="commissions")
    organization = models.ForeignKey(
        "organizations.Organization", null=True, blank=True, on_delete=models.SET_NULL, related_name="commissions"
    )
    dealership = models.ForeignKey(
        "organizations.Organization", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="dealer_commissions",
    )
    rate = models.DecimalField(max_digits=5, decimal_places=2, default=10)
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING, db_index=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    notes = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Commission {self.amount} for {self.policy.policy_number}"
