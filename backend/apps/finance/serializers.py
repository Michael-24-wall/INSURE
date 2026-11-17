from rest_framework import serializers

from .models import (
    CurrencyConfig,
    ExchangeRate,
    JournalEntry,
    LedgerAccount,
    LedgerEntry,
    PlatformFee,
    Settlement,
)


class LedgerAccountSerializer(serializers.ModelSerializer):
    class Meta:
        model = LedgerAccount
        fields = (
            "id", "code", "name", "type", "currency", "is_active", "description", "created_at",
        )
        read_only_fields = ("id", "created_at")


class LedgerEntrySerializer(serializers.ModelSerializer):
    account_code = serializers.CharField(source="account.code", read_only=True)
    account_name = serializers.CharField(source="account.name", read_only=True)
    account_type = serializers.CharField(source="account.type", read_only=True)

    class Meta:
        model = LedgerEntry
        fields = (
            "id", "journal_entry", "account", "account_code", "account_name", "account_type",
            "direction", "amount", "currency", "reference", "created_at",
        )
        read_only_fields = fields


class JournalEntrySerializer(serializers.ModelSerializer):
    entries = LedgerEntrySerializer(many=True, read_only=True)
    posted_by_email = serializers.EmailField(source="posted_by.email", read_only=True)

    class Meta:
        model = JournalEntry
        fields = (
            "id", "reference", "description", "currency", "status", "posted_at", "posted_by",
            "posted_by_email", "reversal_of", "payment", "policy", "claim", "commission",
            "settlement", "metadata", "entries", "created_at",
        )
        read_only_fields = fields


class JournalEntryCreateSerializer(serializers.Serializer):
    """Manually post a balanced journal entry (platform finance only)."""
    reference = serializers.CharField(max_length=40)
    description = serializers.CharField(max_length=255)
    currency = serializers.CharField(max_length=3, default="KES")
    lines = serializers.ListField(child=serializers.DictField(), min_length=2)

    def validate_lines(self, lines):
        for line in lines:
            if "account" not in line or "direction" not in line or "amount" not in line:
                raise serializers.ValidationError("Each line needs account, direction and amount.")
            if line["direction"] not in {"debit", "credit"}:
                raise serializers.ValidationError("Direction must be debit or credit.")
        return lines


class ExchangeRateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExchangeRate
        fields = (
            "id", "from_currency", "to_currency", "rate", "effective_at", "source", "created_at",
        )
        read_only_fields = ("id", "created_at")


class SettlementSerializer(serializers.ModelSerializer):
    insurer_name = serializers.CharField(source="insurer.display_name", read_only=True)

    class Meta:
        model = Settlement
        fields = (
            "id", "reference", "insurer", "insurer_name", "amount_due", "amount_settled",
            "currency", "status", "settlement_instructions", "settlement_reference",
            "settled_at", "settled_by", "reconciliation_notes", "outstanding", "created_at", "updated_at",
        )
        read_only_fields = (
            "id", "reference", "insurer_name", "amount_settled", "status", "settled_at",
            "settled_by", "outstanding", "created_at", "updated_at",
        )


class SettlementCreateSerializer(serializers.Serializer):
    insurer = serializers.UUIDField()
    amount_due = serializers.DecimalField(max_digits=14, decimal_places=2)
    currency = serializers.CharField(max_length=3, default="KES")
    settlement_instructions = serializers.CharField(required=False, allow_blank=True)


class SettlementSettleSerializer(serializers.Serializer):
    settlement_reference = serializers.CharField(max_length=120, required=False, allow_blank=True)
    reconciliation_notes = serializers.CharField(required=False, allow_blank=True)


class CurrencyConfigSerializer(serializers.ModelSerializer):
    class Meta:
        model = CurrencyConfig
        fields = ("id", "country", "default_currency", "supported_currencies", "tax_rate", "is_active", "created_at", "updated_at")
        read_only_fields = ("id", "created_at", "updated_at")


class PlatformFeeSerializer(serializers.ModelSerializer):
    class Meta:
        model = PlatformFee
        fields = ("id", "name", "code", "amount", "currency", "is_active", "description", "created_at", "updated_at")
        read_only_fields = ("id", "created_at", "updated_at")
