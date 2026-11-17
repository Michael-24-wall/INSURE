from rest_framework import serializers

from .models import Commission, Payment, Refund, Transaction


class TransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Transaction
        fields = ("id", "payment", "type", "amount", "status", "reference", "raw_response", "created_at")
        read_only_fields = fields


class RefundSerializer(serializers.ModelSerializer):
    class Meta:
        model = Refund
        fields = ("id", "payment", "amount", "reason", "status", "reference", "processed_by", "completed_at", "created_at")
        read_only_fields = ("id", "payment", "status", "reference", "processed_by", "completed_at", "created_at")


class PaymentSerializer(serializers.ModelSerializer):
    user_email = serializers.EmailField(source="user.email", read_only=True)
    user_name = serializers.CharField(source="user.full_name", read_only=True)
    application_number = serializers.CharField(source="application.application_number", read_only=True)
    policy_number = serializers.CharField(source="policy.policy_number", read_only=True)
    claim_number = serializers.CharField(source="claim.claim_number", read_only=True)
    transactions = TransactionSerializer(many=True, read_only=True)
    refunds = RefundSerializer(many=True, read_only=True)
    can_verify = serializers.SerializerMethodField()

    class Meta:
        model = Payment
        fields = (
            "id", "reference", "user", "user_email", "user_name", "purpose", "application",
            "application_number", "policy", "policy_number", "claim", "claim_number",
            "inspection", "amount", "currency", "method", "status", "provider",
            "provider_reference", "checkout_request_id", "merchant_reference", "phone",
            "metadata", "failure_reason", "verified_at", "receipt_number", "transactions",
            "refunds", "can_verify", "created_at", "updated_at",
        )
        read_only_fields = fields

    def get_can_verify(self, obj):
        return obj.status in {Payment.Status.PENDING, Payment.Status.PROCESSING}


class InitiatePaymentSerializer(serializers.Serializer):
    application = serializers.UUIDField()
    method = serializers.ChoiceField(choices=Payment.Method.choices)
    phone = serializers.CharField(max_length=30, required=False, allow_blank=True)


class VerifyPaymentSerializer(serializers.Serializer):
    provider_reference = serializers.CharField(max_length=120)
    notes = serializers.CharField(required=False, allow_blank=True)


class RefundCreateSerializer(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=14, decimal_places=2)
    reason = serializers.CharField()

    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError("Refund amount must be positive.")
        return value


class CommissionSerializer(serializers.ModelSerializer):
    policy_number = serializers.CharField(source="policy.policy_number", read_only=True)
    agent_name = serializers.CharField(source="agent.full_name", read_only=True)
    agent_email = serializers.EmailField(source="agent.email", read_only=True)
    organization_name = serializers.CharField(source="organization.name", read_only=True)
    dealership_name = serializers.CharField(source="dealership.name", read_only=True)

    class Meta:
        model = Commission
        fields = (
            "id", "policy", "policy_number", "agent", "agent_name", "agent_email",
            "organization", "organization_name", "dealership", "dealership_name",
            "rate", "amount", "status", "paid_at", "notes", "created_at",
        )
        read_only_fields = ("id", "policy_number", "agent_name", "agent_email", "organization_name", "dealership_name", "paid_at", "created_at")


class CommissionCreateSerializer(serializers.Serializer):
    policy = serializers.UUIDField()
    agent = serializers.UUIDField(required=False)
    rate = serializers.DecimalField(max_digits=5, decimal_places=2, required=False)
    notes = serializers.CharField(required=False, allow_blank=True)
