from rest_framework import serializers

from .adapters import outbound_url_error
from .models import Integration, IntegrationLog, WebhookEvent


class IntegrationSerializer(serializers.ModelSerializer):
    organization_name = serializers.CharField(source="organization.name", read_only=True)
    credentials = serializers.CharField(write_only=True, required=False, allow_blank=True)
    webhook_secret = serializers.CharField(write_only=True, required=False, allow_blank=True)

    class Meta:
        model = Integration
        fields = (
            "id", "organization", "organization_name", "name", "provider_type", "base_url",
            "auth_type", "config", "timeout_seconds", "retry_limit", "is_enabled", "status",
            "last_tested_at", "last_error", "credentials", "webhook_secret", "created_at", "updated_at",
        )
        read_only_fields = ("id", "status", "last_tested_at", "last_error", "created_at", "updated_at")

    def validate_base_url(self, value):
        error = outbound_url_error(value)
        if error:
            raise serializers.ValidationError(error)
        return value

    def create(self, validated_data):
        credentials = validated_data.pop("credentials", "")
        webhook_secret = validated_data.pop("webhook_secret", "")
        integration = Integration.objects.create(**validated_data)
        if credentials:
            integration.set_credentials(credentials)
        if webhook_secret:
            integration.set_webhook_secret(webhook_secret)
        integration.save()
        return integration

    def update(self, instance, validated_data):
        credentials = validated_data.pop("credentials", None)
        webhook_secret = validated_data.pop("webhook_secret", None)
        for k, v in validated_data.items():
            setattr(instance, k, v)
        if credentials:
            instance.set_credentials(credentials)
        if webhook_secret:
            instance.set_webhook_secret(webhook_secret)
        instance.save()
        return instance


class IntegrationLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = IntegrationLog
        fields = (
            "id", "integration", "direction", "endpoint", "method", "request_payload",
            "response_payload", "status_code", "success", "duration_ms", "error", "attempt", "created_at",
        )
        read_only_fields = fields


class WebhookEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = WebhookEvent
        fields = ("id", "provider", "event_id", "event_type", "signature_valid", "processed", "processed_at", "error", "created_at")
        read_only_fields = fields
