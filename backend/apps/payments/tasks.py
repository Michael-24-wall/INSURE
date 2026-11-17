"""Celery tasks for payment automation and reconciliation."""
import logging

from celery import shared_task
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task
def process_mpesa_callback(payload):
    """Async variant of the M-Pesa STK callback handler."""
    from .services import handle_stk_callback

    try:
        return handle_stk_callback(payload)
    except Exception:  # pragma: no cover - never raise out of a webhook task
        logger.exception("M-Pesa callback processing failed")
        return {"result_code": 0, "result_desc": "Error", "applied": False}


@shared_task
def reconcile_pending_mpesa():
    """Query Daraja for PROCESSING M-Pesa payments and settle them."""
    from .gateways import GatewayError, MpesaDarajaClient
    from .models import Payment
    from .services import complete_payment, fail_payment

    client = MpesaDarajaClient()
    if not client.configured:
        return 0

    payments = (
        Payment.objects.filter(method=Payment.Method.MPESA, status=Payment.Status.PROCESSING)
        .exclude(checkout_request_id="")
    )
    settled = 0
    for payment in payments:
        try:
            query = client.query(payment.checkout_request_id)
        except GatewayError:
            continue
        if str(query.get("ResultCode")) == "0":
            complete_payment(payment.id, provider_reference=payment.provider_reference, raw=query)
        else:
            fail_payment(payment.id, query.get("ResultDesc", "Payment failed"))
        settled += 1
    return settled


@shared_task
def reconcile_pending_card():
    """Verify PROCESSING card payments against Flutterwave."""
    from .gateways import FlutterwaveCardGateway
    from .models import Payment
    from .services import verify_card_payment

    if not FlutterwaveCardGateway().configured:
        return 0

    payments = Payment.objects.filter(method=Payment.Method.CARD, status=Payment.Status.PROCESSING)
    settled = 0
    for payment in payments:
        try:
            verify_card_payment(payment.id)
            settled += 1
        except Exception:
            logger.exception("Card reconciliation failed for payment %s", payment.id)
    return settled


@shared_task
def timeout_stale_payments():
    """Fail payments that have been pending for too long.

    M-Pesa/card PROCESSING payments are left to the reconciliation tasks; this
    only clears genuinely abandoned PENDING records.
    """
    from .models import Payment
    from .services import fail_payment

    now = timezone.now()
    mpesa_cutoff = now - timezone.timedelta(minutes=settings.PAYMENT_MPESA_TIMEOUT_MINUTES)
    bank_cutoff = now - timezone.timedelta(days=settings.PAYMENT_BANK_TIMEOUT_DAYS)
    card_cutoff = now - timezone.timedelta(minutes=settings.PAYMENT_CARD_TIMEOUT_MINUTES)

    timed_out = (
        Payment.objects.filter(status=Payment.Status.PENDING, method=Payment.Method.MPESA, created_at__lt=mpesa_cutoff)
        | Payment.objects.filter(status=Payment.Status.PENDING, method=Payment.Method.CARD, created_at__lt=card_cutoff)
        | Payment.objects.filter(status=Payment.Status.PENDING, method=Payment.Method.BANK, created_at__lt=bank_cutoff)
    )
    failed = 0
    for payment in timed_out.distinct():
        try:
            fail_payment(payment.id, "Timed out awaiting confirmation.")
            failed += 1
        except Exception:
            logger.exception("Failed to time out payment %s", payment.id)
    return failed
