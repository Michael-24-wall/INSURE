import uuid

from django.db import models

from apps.common.models import TimeStampedModel

from .crypto import decrypt, encrypt


class Integration(TimeStampedModel):
    class ProviderType(models.TextChoices):
        REST = "rest", "REST API"
        WEBHOOK = "webhook", "Webhook"
        SOAP = "soap", "SOAP"
        SFTP = "sftp", "SFTP"
        MANUAL = "manual", "Manual / Offline"

    class Status(models.TextChoices):
        INACTIVE = "inactive", "Inactive"
        ACTIVE = "active", "Active"
        DEGRADED = "degraded", "Degraded"
        ERROR = "error", "Error"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.CASCADE, related_name="integrations"
    )
    name = models.CharField(max_length=150)
    provider_type = models.CharField(max_length=20, choices=ProviderType.choices, default=ProviderType.REST)
    base_url = models.URLField(blank=True)
    auth_type = models.CharField(
        max_length=20,
        choices=[("none", "None"), ("api_key", "API Key"), ("bearer", "Bearer Token"), ("basic", "Basic Auth"), ("hmac", "HMAC")],
        default="api_key",
    )
    credentials_encrypted = models.TextField(blank=True)
    config = models.JSONField(default=dict, blank=True)
    webhook_secret_encrypted = models.TextField(blank=True)
    timeout_seconds = models.PositiveIntegerField(default=20)
    retry_limit = models.PositiveIntegerField(default=3)
    is_enabled = models.BooleanField(default=False)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.INACTIVE)
    last_tested_at = models.DateTimeField(null=True, blank=True)
    last_error = models.TextField(blank=True)

    class Meta:
        ordering = ["organization__name", "name"]
        unique_together = ("organization", "name")

    def __str__(self):
        return f"{self.organization.name} - {self.name}"

    def set_credentials(self, value: str):
        self.credentials_encrypted = encrypt(value)

    def get_credentials(self):
        return decrypt(self.credentials_encrypted)

    def set_webhook_secret(self, value: str):
        self.webhook_secret_encrypted = encrypt(value)

    def get_webhook_secret(self):
        return decrypt(self.webhook_secret_encrypted)


class IntegrationLog(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    integration = models.ForeignKey(Integration, on_delete=models.CASCADE, related_name="logs")
    direction = models.CharField(max_length=10, choices=[("outbound", "Outbound"), ("inbound", "Inbound")])
    endpoint = models.CharField(max_length=255, blank=True)
    method = models.CharField(max_length=10, blank=True)
    request_payload = models.JSONField(default=dict, blank=True)
    response_payload = models.JSONField(default=dict, blank=True)
    status_code = models.PositiveIntegerField(null=True, blank=True)
    success = models.BooleanField(default=False)
    duration_ms = models.PositiveIntegerField(null=True, blank=True)
    error = models.TextField(blank=True)
    attempt = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]


class WebhookEvent(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    provider = models.CharField(max_length=50, db_index=True)
    event_id = models.CharField(max_length=200)
    event_type = models.CharField(max_length=100, blank=True)
    payload = models.JSONField(default=dict, blank=True)
    signature_valid = models.BooleanField(default=False)
    processed = models.BooleanField(default=False)
    processed_at = models.DateTimeField(null=True, blank=True)
    error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        unique_together = ("provider", "event_id")

    def __str__(self):
        return f"{self.provider}:{self.event_id}"
