from django.contrib import admin

from .models import Integration, IntegrationLog, WebhookEvent


@admin.register(Integration)
class IntegrationAdmin(admin.ModelAdmin):
    list_display = ("organization", "name", "provider_type", "status", "is_enabled", "last_tested_at")
    list_filter = ("provider_type", "status", "is_enabled")
    search_fields = ("organization__name", "name", "base_url")
    exclude = ("credentials_encrypted", "webhook_secret_encrypted")


@admin.register(IntegrationLog)
class IntegrationLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "integration", "direction", "endpoint", "status_code", "success", "duration_ms")
    list_filter = ("direction", "success")
    readonly_fields = [f.name for f in IntegrationLog._meta.fields]


@admin.register(WebhookEvent)
class WebhookEventAdmin(admin.ModelAdmin):
    list_display = ("provider", "event_id", "event_type", "signature_valid", "processed", "created_at")
    list_filter = ("provider", "signature_valid", "processed")
    readonly_fields = [f.name for f in WebhookEvent._meta.fields]
