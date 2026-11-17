"""Financial ledger, settlement and currency models.

This app is the accounting layer for INSURECONNECT. It does not replace the
payment gateway engine in ``apps.payments``; it records the double-entry
ledger postings that payment, commission, settlement and refund operations
feed into. Every posted journal entry is balanced (debits == credits) and
immutable; corrections are made by reversal entries.
"""
import uuid

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone

from apps.common.models import TimeStampedModel


class LedgerAccount(models.Model):
    """Chart of accounts. One currency per account; no silent conversion."""

    class Type(models.TextChoices):
        ASSET = "asset", "Asset"
        LIABILITY = "liability", "Liability"
        EQUITY = "equity", "Equity"
        REVENUE = "revenue", "Revenue"
        EXPENSE = "expense", "Expense"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(max_length=20, unique=True, db_index=True)
    name = models.CharField(max_length=200)
    type = models.CharField(max_length=20, choices=Type.choices, db_index=True)
    currency = models.CharField(max_length=3, default="KES")
    is_active = models.BooleanField(default=True)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["code"]
        verbose_name_plural = "ledger accounts"

    def __str__(self):
        return f"{self.code} - {self.name}"


class JournalEntry(models.Model):
    """Header of a double-entry posting. Posted entries are immutable."""

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        POSTED = "posted", "Posted"
        REVERSED = "reversed", "Reversed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    reference = models.CharField(max_length=40, unique=True, db_index=True)
    description = models.CharField(max_length=255)
    currency = models.CharField(max_length=3, default="KES")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT, db_index=True)
    posted_at = models.DateTimeField(null=True, blank=True)
    posted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="posted_journal_entries",
    )
    reversal_of = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.SET_NULL, related_name="reversals",
        help_text="Original journal entry this entry reverses.",
    )
    payment = models.ForeignKey("payments.Payment", null=True, blank=True, on_delete=models.SET_NULL, related_name="journal_entries")
    policy = models.ForeignKey("insurance.Policy", null=True, blank=True, on_delete=models.SET_NULL, related_name="journal_entries")
    claim = models.ForeignKey("claims.Claim", null=True, blank=True, on_delete=models.SET_NULL, related_name="journal_entries")
    commission = models.ForeignKey("payments.Commission", null=True, blank=True, on_delete=models.SET_NULL, related_name="journal_entries")
    settlement = models.ForeignKey("finance.Settlement", null=True, blank=True, on_delete=models.SET_NULL, related_name="journal_entries")
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.reference

    @property
    def is_posted(self):
        return self.status == self.Status.POSTED


class LedgerEntry(models.Model):
    """A single debit or credit line within a journal entry."""

    class Direction(models.TextChoices):
        DEBIT = "debit", "Debit"
        CREDIT = "credit", "Credit"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    journal_entry = models.ForeignKey(JournalEntry, on_delete=models.CASCADE, related_name="entries")
    account = models.ForeignKey(LedgerAccount, on_delete=models.PROTECT, related_name="entries")
    direction = models.CharField(max_length=10, choices=Direction.choices, db_index=True)
    amount = models.DecimalField(max_digits=14, decimal_places=2, validators=[MinValueValidator(0)])
    currency = models.CharField(max_length=3, default="KES")
    reference = models.CharField(max_length=120, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.direction} {self.amount} {self.currency} -> {self.account.code}"


class ExchangeRate(models.Model):
    """Historical exchange-rate reference. Never used for silent conversion."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    from_currency = models.CharField(max_length=3, db_index=True)
    to_currency = models.CharField(max_length=3, db_index=True)
    rate = models.DecimalField(max_digits=14, decimal_places=6)
    effective_at = models.DateTimeField(db_index=True)
    source = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-effective_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["from_currency", "to_currency", "effective_at"],
                name="unique_exchange_rate",
            )
        ]

    def __str__(self):
        return f"{self.from_currency}->{self.to_currency} {self.rate} @ {self.effective_at.date()}"


class Settlement(models.Model):
    """Amounts owed to an insurer and their settlement/reconciliation."""

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        INSTRUCTED = "instructed", "Instructed"
        SETTLED = "settled", "Settled"
        RECONCILED = "reconciled", "Reconciled"
        FAILED = "failed", "Failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    reference = models.CharField(max_length=40, unique=True, db_index=True)
    insurer = models.ForeignKey("insurance.Insurer", on_delete=models.PROTECT, related_name="settlements")
    amount_due = models.DecimalField(max_digits=14, decimal_places=2, validators=[MinValueValidator(0)])
    amount_settled = models.DecimalField(max_digits=14, decimal_places=2, default=0, validators=[MinValueValidator(0)])
    currency = models.CharField(max_length=3, default="KES")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING, db_index=True)
    settlement_instructions = models.TextField(blank=True)
    settlement_reference = models.CharField(max_length=120, blank=True)
    settled_at = models.DateTimeField(null=True, blank=True)
    settled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="executed_settlements",
    )
    reconciliation_notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.reference

    @property
    def outstanding(self):
        return self.amount_due - self.amount_settled


class CurrencyConfig(models.Model):
    """Country-specific financial configuration (default currency, tax rate)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    country = models.CharField(max_length=100, unique=True, db_index=True)
    default_currency = models.CharField(max_length=3, default="KES")
    supported_currencies = models.JSONField(default=list, blank=True)
    tax_rate = models.DecimalField(max_digits=5, decimal_places=4, default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["country"]

    def __str__(self):
        return self.country


class PlatformFee(models.Model):
    """Configured platform fees. Revenue is recognised from ledger postings to
    the platform revenue account; this table holds the fee configuration only.
    The platform never holds or distributes insurance premiums itself."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200)
    code = models.CharField(max_length=40, unique=True)
    amount = models.DecimalField(max_digits=14, decimal_places=2, validators=[MinValueValidator(0)])
    currency = models.CharField(max_length=3, default="KES")
    is_active = models.BooleanField(default=True)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["code"]

    def __str__(self):
        return self.code
