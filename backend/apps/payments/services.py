import logging
from decimal import Decimal

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.common.utils import generate_reference
from apps.notifications.services import notify

from .gateways import (
    FlutterwaveCardGateway,
    GatewayError,
    GatewayNotConfigured,
    MpesaDarajaClient,
    normalize_phone,
)
from .models import Payment, Refund, Transaction

logger = logging.getLogger(__name__)


class PaymentError(Exception):
    pass


def initiate_premium_payment(user, application, method, phone="", idempotency_key=None):
    from apps.insurance.models import Application

    if application.customer_id != user.id:
        raise PaymentError("You can only pay for your own application.")
    if application.status not in {
        Application.Status.SUBMITTED,
        Application.Status.UNDER_REVIEW,
        Application.Status.MORE_INFO,
        Application.Status.APPROVED,
    }:
        raise PaymentError("This application is not open for payment.")
    if Payment.objects.filter(
        application=application, purpose=Payment.Purpose.PREMIUM, status=Payment.Status.SUCCEEDED
    ).exists():
        raise PaymentError("This application has already been paid.")

    if idempotency_key:
        existing = Payment.objects.filter(idempotency_key=idempotency_key).first()
        if existing:
            if existing.user_id != user.id:
                raise PaymentError("This idempotency key has already been used.")
            return existing, False

    amount = application.quotation.premium
    payment = Payment.objects.create(
        user=user,
        purpose=Payment.Purpose.PREMIUM,
        application=application,
        amount=amount,
        method=method,
        status=Payment.Status.PENDING,
        idempotency_key=idempotency_key or None,
        phone=normalize_phone(phone) if phone else "",
        provider=method,
    )

    if method == Payment.Method.MPESA:
        client = MpesaDarajaClient()
        if client.configured:
            try:
                result = client.stk_push(
                    normalize_phone(phone), int(amount), payment.reference, "Insurance premium"
                )
                payment.status = Payment.Status.PROCESSING
                payment.checkout_request_id = result.get("CheckoutRequestID", "")
                payment.merchant_reference = result.get("MerchantRequestID", "")
                payment.metadata = {"gateway": "daraja", "response": result}
                payment.save(update_fields=["status", "checkout_request_id", "merchant_reference", "metadata"])
            except (GatewayError, GatewayNotConfigured) as exc:
                payment.status = Payment.Status.FAILED
                payment.failure_reason = str(exc)[:255]
                payment.save(update_fields=["status", "failure_reason"])
                raise PaymentError(str(exc))
        else:
            payment.metadata = {
                "gateway_configured": False,
                "instructions": (
                    "M-Pesa credentials are not configured. This payment is pending and must be "
                    "reconciled by authorised provider staff once funds are received."
                ),
                "paybill": settings.M_PESA_SHORTCODE or "not configured",
            }
            payment.save(update_fields=["metadata"])
    elif method == Payment.Method.BANK:
        payment.metadata = {
            "gateway_configured": False,
            "instructions": (
                "Record the bank transfer reference after paying to the insurer collection account. "
                "An authorised staff member must verify the payment before the policy is issued."
            ),
        }
        payment.save(update_fields=["metadata"])
    elif method == Payment.Method.CARD:
        gateway = FlutterwaveCardGateway()
        if not gateway.configured:
            payment.status = Payment.Status.FAILED
            payment.failure_reason = "Card gateway is not configured. Use M-Pesa or bank transfer."
            payment.save(update_fields=["status", "failure_reason"])
            raise PaymentError(payment.failure_reason)
        try:
            link = gateway.initiate(
                amount=amount,
                currency=payment.currency,
                tx_ref=payment.reference,
                redirect_url=settings.CARD_REDIRECT_URL,
                email=user.email,
                name=user.full_name,
                phone=normalize_phone(phone) if phone else "",
            )
            payment.status = Payment.Status.PROCESSING
            payment.metadata = {"gateway": "flutterwave", "checkout_link": link, "tx_ref": payment.reference}
            payment.save(update_fields=["status", "metadata"])
        except (GatewayError, GatewayNotConfigured) as exc:
            payment.status = Payment.Status.FAILED
            payment.failure_reason = str(exc)[:255]
            payment.save(update_fields=["status", "failure_reason"])
            raise PaymentError(str(exc))
    return payment, True


@transaction.atomic
def complete_payment(payment_id, provider_reference="", raw=None, actor=None):
    payment = Payment.objects.select_for_update().get(pk=payment_id)
    if payment.status == Payment.Status.SUCCEEDED:
        return payment
    if payment.status not in {Payment.Status.PENDING, Payment.Status.PROCESSING}:
        raise PaymentError("Only pending or processing payments can be completed.")
    payment.status = Payment.Status.SUCCEEDED
    payment.provider_reference = provider_reference or payment.provider_reference
    payment.verified_at = timezone.now()
    payment.verified_by = actor
    payment.receipt_number = payment.receipt_number or generate_reference("RCPT", 8)
    payment.save(
        update_fields=["status", "provider_reference", "verified_at", "verified_by", "receipt_number"]
    )
    # Double-entry ledger: verified payment is received funds. Post only once
    # per successful transition so retries/callbacks do not double-post.
    if payment.purpose == Payment.Purpose.PREMIUM:
        from apps.finance.services import post_journal_entry

        post_journal_entry(
            reference=f"PAY-{payment.reference}",
            description=f"Premium payment received for {payment.reference}",
            lines=[
                {"account": "1000", "direction": "debit", "amount": payment.amount, "reference": payment.reference},
                {
                    "account": "2000",
                    "direction": "credit",
                    "amount": payment.amount,
                    "reference": payment.reference,
                },
            ],
            currency=payment.currency,
            posted_by=actor,
            payment=payment,
        )
    Transaction.objects.create(
        payment=payment,
        type=Transaction.Type.CHARGE,
        amount=payment.amount,
        status=Transaction.Status.SUCCEEDED,
        reference=payment.provider_reference or payment.reference,
        raw_response=raw or {},
    )
    notify(
        payment.user,
        "Payment received",
        f"Payment {payment.reference} of {payment.amount} {payment.currency} was confirmed. Receipt {payment.receipt_number}.",
        "payment",
        f"/customer/payments/{payment.id}",
    )
    return payment


@transaction.atomic
def fail_payment(payment_id, reason=""):
    payment = Payment.objects.select_for_update().get(pk=payment_id)
    if payment.status == Payment.Status.SUCCEEDED:
        raise PaymentError("A successful payment cannot be failed.")
    payment.status = Payment.Status.FAILED
    payment.failure_reason = reason[:255]
    payment.save(update_fields=["status", "failure_reason"])
    Transaction.objects.create(
        payment=payment,
        type=Transaction.Type.CHARGE,
        amount=payment.amount,
        status=Transaction.Status.FAILED,
        reference=payment.provider_reference,
        raw_response={"reason": reason},
    )
    notify(payment.user, "Payment failed", f"Payment {payment.reference} failed: {reason}", "payment")
    return payment


@transaction.atomic
def create_refund(payment, amount, reason, actor):
    from django.db.models import Sum

    if payment.status != Payment.Status.SUCCEEDED:
        raise PaymentError("Only successful payments can be refunded.")
    refunded = payment.refunds.filter(status=Refund.Status.COMPLETED).aggregate(total=Sum("amount"))["total"] or Decimal("0")
    if refunded + amount > payment.amount:
        raise PaymentError("Refund amount exceeds the remaining refundable balance.")
    refund = Refund.objects.create(
        payment=payment,
        amount=amount,
        reason=reason,
        status=Refund.Status.COMPLETED,
        reference=generate_reference("REF", 8),
        processed_by=actor,
        completed_at=timezone.now(),
    )
    # Double-entry ledger: reverse the premium receipt when refunded.
    if payment.purpose == Payment.Purpose.PREMIUM:
        from apps.finance.services import post_journal_entry

        post_journal_entry(
            reference=f"REFUND-{refund.reference}",
            description=f"Premium refund {refund.reference} for {payment.reference}",
            lines=[
                {"account": "2000", "direction": "debit", "amount": amount, "reference": refund.reference},
                {"account": "1000", "direction": "credit", "amount": amount, "reference": refund.reference},
            ],
            currency=payment.currency,
            posted_by=actor,
            payment=payment,
        )
    Transaction.objects.create(
        payment=payment,
        type=Transaction.Type.REFUND,
        amount=-amount,
        status=Transaction.Status.SUCCEEDED,
        reference=refund.reference,
        raw_response={"reason": reason},
    )
    if refunded + amount >= payment.amount:
        payment.status = Payment.Status.REFUNDED
        payment.save(update_fields=["status"])
    notify(payment.user, "Refund processed", f"A refund of {amount} was processed for {payment.reference}.", "payment")
    return refund


def gateway_status():
    client = MpesaDarajaClient()
    card = FlutterwaveCardGateway()
    return {
        "mpesa_configured": client.configured,
        "mpesa_env": client.env,
        "card_configured": card.configured,
        "bank_manual": True,
    }


def _metadata_item(items, name):
    for item in items or []:
        if isinstance(item, dict) and item.get("Name") == name:
            return item.get("Value")
    return None


def handle_stk_callback(payload):
    """Process an M-Pesa STK push callback. Idempotent via WebhookEvent.

    The authoritative confirmation is the Daraja STK query: the callback alone
    is never trusted to mark a payment successful.
    """
    from apps.integrations.models import WebhookEvent

    body = payload.get("Body", {}) if isinstance(payload, dict) else {}
    stk = body.get("stkCallback", {})
    checkout_id = stk.get("CheckoutRequestID", "")
    result_code = stk.get("ResultCode")
    metadata_items = stk.get("CallbackMetadata", {}).get("Item", []) if isinstance(stk.get("CallbackMetadata"), dict) else []
    callback_amount = _metadata_item(metadata_items, "Amount")
    event_id = f"{checkout_id}:{result_code}:{callback_amount}"

    event, created = WebhookEvent.objects.get_or_create(
        provider="mpesa",
        event_id=event_id,
        defaults={"event_type": "stk_callback", "payload": payload},
    )
    if not created and event.processed:
        return {"result_code": 0, "result_desc": "Already processed", "applied": False}

    client = MpesaDarajaClient()
    if not client.configured:
        event.error = "M-Pesa gateway not configured; callback logged but not applied."
        event.save(update_fields=["error"])
        return {"result_code": 0, "result_desc": "Logged for manual reconciliation", "applied": False}

    payment = Payment.objects.filter(checkout_request_id=checkout_id).first()
    if not payment:
        event.error = "Unknown checkout request id."
        event.save(update_fields=["error"])
        return {"result_code": 0, "result_desc": "Unknown payment", "applied": False}

    if callback_amount is not None and Decimal(str(callback_amount)) != payment.amount:
        event.error = "Callback amount does not match the initiated payment."
        event.save(update_fields=["error"])
        return {"result_code": 0, "result_desc": "Amount mismatch", "applied": False}

    try:
        query = client.query(checkout_id)
    except GatewayError as exc:
        event.error = str(exc)
        event.save(update_fields=["error"])
        return {"result_code": 0, "result_desc": "Pending verification", "applied": False}

    query_amount = query.get("Amount")
    if query_amount is not None and Decimal(str(query_amount)) != payment.amount:
        event.error = "Verified gateway amount does not match the initiated payment."
        event.save(update_fields=["error"])
        return {"result_code": 0, "result_desc": "Amount mismatch", "applied": False}

    receipt = _metadata_item(metadata_items, "MpesaReceiptNumber") or query.get("MpesaReceiptNumber", "")
    event.signature_valid = True
    try:
        if str(query.get("ResultCode")) == "0":
            complete_payment(payment.id, provider_reference=receipt, raw=payload)
        else:
            fail_payment(payment.id, stk.get("ResultDesc", "Payment failed"))
        event.processed = True
    except PaymentError as exc:
        event.error = str(exc)

    event.processed_at = timezone.now()
    event.save()
    return {"result_code": 0, "result_desc": "Accepted", "applied": True}


@transaction.atomic
def verify_card_payment(payment_id):
    """Authoritatively confirm a card payment via Flutterwave."""
    payment = Payment.objects.select_for_update().get(pk=payment_id)
    gateway = FlutterwaveCardGateway()
    if not gateway.configured:
        return payment
    tx_ref = (payment.metadata or {}).get("tx_ref") or payment.reference
    result = gateway.verify(tx_ref)
    data = result.get("data") or {}
    status = data.get("status")
    amount = data.get("amount")
    currency = data.get("currency")
    if status == "successful":
        if amount is None or Decimal(str(amount)) != payment.amount:
            raise PaymentError("Verified gateway amount does not match the initiated payment.")
        if currency and str(currency).upper() != payment.currency.upper():
            raise PaymentError("Verified gateway currency does not match the initiated payment.")
        complete_payment(payment.id, provider_reference=data.get("flw_ref", ""), raw=result)
    elif status in {"failed", "cancelled"}:
        fail_payment(payment.id, data.get("processor_response", "Card payment failed"))
    return payment
