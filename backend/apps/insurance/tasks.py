"""Celery tasks for the insurance lifecycle: expiry, lapse and renewals."""
import logging
from datetime import timedelta

from celery import shared_task
from django.conf import settings
from django.utils import timezone

from apps.notifications.services import notify

from .models import Policy, Quotation, QuotationRequest

logger = logging.getLogger(__name__)


@shared_task
def expire_quotation_requests():
    """Mark quotation requests (and their open quotations) as expired."""
    now = timezone.now()
    requests = QuotationRequest.objects.filter(
        status__in=[
            QuotationRequest.Status.PENDING,
            QuotationRequest.Status.UNDER_REVIEW,
            QuotationRequest.Status.MORE_INFO,
            QuotationRequest.Status.QUOTED,
            QuotationRequest.Status.SELECTED,
        ],
        expires_at__lte=now,
    )
    count = 0
    for req in requests:
        req.status = QuotationRequest.Status.EXPIRED
        req.save(update_fields=["status"])
        req.quotations.filter(
            status__in=[Quotation.Status.RECEIVED, Quotation.Status.MORE_INFO]
        ).update(status=Quotation.Status.EXPIRED)
        count += 1
    return count


@shared_task
def lapse_expired_policies():
    """Move active policies whose cover period has ended to expired."""
    today = timezone.now().date()
    policies = Policy.objects.filter(status=Policy.Status.ACTIVE, end_date__lt=today)
    updated = policies.update(status=Policy.Status.EXPIRED)
    return updated


@shared_task
def push_quotation_request_to_integrations(request_id):
    """Best-effort push of a quotation request to enabled insurer integrations.

    No-op when no integrations are enabled. Failures are logged and skipped so
    the synchronous quotation flow is never blocked by a provider outage.
    """
    from apps.integrations.adapters import IntegrationCallError, IntegrationNotConfigured, get_adapter
    from apps.integrations.models import Integration
    from apps.insurance.models import QuotationRequest

    req = QuotationRequest.objects.select_related("vehicle").filter(pk=request_id).first()
    if not req:
        return 0

    integrations = Integration.objects.filter(
        is_enabled=True,
        provider_type__in=[Integration.ProviderType.REST, Integration.ProviderType.WEBHOOK],
    )
    payload = {
        "request_number": req.request_number,
        "coverage_type": req.coverage_type,
        "sum_insured": str(req.sum_insured),
        "desired_start_date": req.desired_start_date.isoformat(),
        "vehicle": {
            "registration_number": req.vehicle.registration_number,
            "make": req.vehicle.make,
            "model": req.vehicle.model,
            "year": req.vehicle.manufacturing_year,
            "value": str(req.vehicle.estimated_value),
        },
    }
    pushed = 0
    for integration in integrations:
        try:
            get_adapter(integration).push_quotation_request(payload)
            pushed += 1
        except (IntegrationCallError, IntegrationNotConfigured) as exc:
            logger.info("Integration push skipped for %s: %s", integration.name, exc)
    return pushed


@shared_task
def send_renewal_reminders():
    """Notify policyholders of policies expiring within the reminder window."""
    today = timezone.now().date()
    window_days = int(getattr(settings, "POLICY_RENEWAL_REMINDER_DAYS", 30))
    horizon = today + timedelta(days=window_days)

    policies = Policy.objects.filter(
        status=Policy.Status.ACTIVE,
        end_date__gte=today,
        end_date__lte=horizon,
        renewal_reminder_sent_at__isnull=True,
    ).select_related("customer", "vehicle")
    sent = 0
    for policy in policies:
        notify(
            policy.customer,
            "Policy renewal reminder",
            f"Your policy {policy.policy_number} for {policy.vehicle.registration_number} "
            f"expires on {policy.end_date}. Renew to keep your cover active.",
            "policy",
            f"/customer/policies/{policy.id}",
        )
        policy.renewal_reminder_sent_at = timezone.now()
        policy.save(update_fields=["renewal_reminder_sent_at"])
        sent += 1
    return sent
