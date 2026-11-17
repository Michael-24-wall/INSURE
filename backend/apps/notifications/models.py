import uuid

from django.conf import settings
from django.db import models

from apps.common.models import TimeStampedModel


class Notification(TimeStampedModel):
    class Category(models.TextChoices):
        ACCOUNT = "account", "Account"
        ORGANIZATION = "organization", "Organization"
        QUOTATION = "quotation", "Quotation"
        APPLICATION = "application", "Application"
        POLICY = "policy", "Policy"
        INSPECTION = "inspection", "Inspection"
        CLAIM = "claim", "Claim"
        PAYMENT = "payment", "Payment"
        SYSTEM = "system", "System"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications")
    title = models.CharField(max_length=200)
    message = models.TextField()
    category = models.CharField(max_length=30, choices=Category.choices, default=Category.SYSTEM)
    link = models.CharField(max_length=255, blank=True)
    is_read = models.BooleanField(default=False, db_index=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user.email}: {self.title}"


class Message(TimeStampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="sent_messages")
    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="received_messages")
    subject = models.CharField(max_length=200, blank=True)
    body = models.TextField()
    claim = models.ForeignKey("claims.Claim", null=True, blank=True, on_delete=models.CASCADE, related_name="messages")
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.sender.email} -> {self.recipient.email}"
