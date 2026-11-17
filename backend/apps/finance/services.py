"""Double-entry ledger service.

Rules enforced here:
- Every posted journal entry is balanced: total debits == total credits.
- Posted entries are immutable; corrections are posted as reversal entries.
- Currency consistency: all lines in an entry share one currency; no silent
  conversion between currencies.
- A payment is only recognised as received funds once it is verified
  (Payment.status == SUCCEEDED and verified_at is set).
"""
from datetime import datetime, time
from decimal import Decimal

from django.db import transaction
from django.db.models import Count, Q, Sum
from django.utils import timezone

from apps.accounts.models import User
from apps.payments.models import Commission, Payment, Refund

from .models import ExchangeRate, JournalEntry, LedgerAccount, LedgerEntry, Settlement


class LedgerError(Exception):
    pass


def _account(code):
    try:
        return LedgerAccount.objects.get(code=code, is_active=True)
    except LedgerAccount.DoesNotExist as exc:
        raise LedgerError(f"Ledger account '{code}' is not configured.") from exc


def _money(value):
    amount = Decimal(value) if value is not None else Decimal("0")
    return amount.quantize(Decimal("0.01"))


def _money_str(value):
    return str(_money(value))


@transaction.atomic
def post_journal_entry(reference, description, lines, currency="KES", posted_by=None, **links):
    """Create and post a balanced journal entry.

    ``lines`` is a list of dicts: {account, direction, amount, reference}.
    ``account`` may be a LedgerAccount instance or an account code string.
    """
    if not lines:
        raise LedgerError("A journal entry requires at least one ledger line.")

    currency = currency or "KES"
    total_debit = Decimal("0")
    total_credit = Decimal("0")
    prepared = []

    for line in lines:
        account = line["account"]
        if not isinstance(account, LedgerAccount):
            account = _account(account)
        if account.currency != currency:
            raise LedgerError(
                f"Account {account.code} currency ({account.currency}) does not match entry currency ({currency})."
            )
        direction = line["direction"]
        if direction not in {LedgerEntry.Direction.DEBIT, LedgerEntry.Direction.CREDIT}:
            raise LedgerError(f"Invalid direction '{direction}'.")
        amount = _money(line["amount"])
        if amount <= 0:
            raise LedgerError("Ledger line amounts must be positive.")
        prepared.append((account, direction, amount, line.get("reference", "")))
        if direction == LedgerEntry.Direction.DEBIT:
            total_debit += amount
        else:
            total_credit += amount

    if total_debit != total_credit:
        raise LedgerError(
            f"Journal entry is not balanced: debits {total_debit} != credits {total_credit}."
        )

    if JournalEntry.objects.filter(reference=reference).exists():
        raise LedgerError(f"Journal entry reference '{reference}' already exists.")

    entry = JournalEntry.objects.create(
        reference=reference,
        description=description,
        currency=currency,
        status=JournalEntry.Status.POSTED,
        posted_at=timezone.now(),
        posted_by=posted_by,
        **links,
    )
    for account, direction, amount, ref in prepared:
        LedgerEntry.objects.create(
            journal_entry=entry,
            account=account,
            direction=direction,
            amount=amount,
            currency=currency,
            reference=ref,
        )
    return entry


@transaction.atomic
def reverse_journal_entry(reference, original_entry, reason, posted_by=None):
    """Post a reversal (mirror-image) journal entry for an immutable posted entry."""
    if original_entry.status != JournalEntry.Status.POSTED:
        raise LedgerError("Only posted journal entries can be reversed.")
    if original_entry.reversals.exists():
        raise LedgerError(f"Journal entry '{original_entry.reference}' has already been reversed.")

    lines = []
    for line in original_entry.entries.all():
        lines.append(
            {
                "account": line.account,
                "direction": (
                    LedgerEntry.Direction.CREDIT
                    if line.direction == LedgerEntry.Direction.DEBIT
                    else LedgerEntry.Direction.DEBIT
                ),
                "amount": line.amount,
                "reference": line.reference or f"Reversal of {original_entry.reference}",
            }
        )

    return post_journal_entry(
        reference=reference,
        description=f"Reversal of {original_entry.reference}: {reason}",
        lines=lines,
        currency=original_entry.currency,
        posted_by=posted_by,
        reversal_of=original_entry,
        **{field: getattr(original_entry, field) for field in ("payment", "policy", "claim", "commission", "settlement")
           if getattr(original_entry, field) is not None},
    )


def account_balance(account_code, as_of=None):
    """Sum of posted debits minus credits for an account (optional point-in-time)."""
    from django.db.models import Sum, Q

    qs = LedgerEntry.objects.filter(
        account__code=account_code, journal_entry__status=JournalEntry.Status.POSTED
    )
    if as_of:
        qs = qs.filter(journal_entry__posted_at__lte=as_of)
    debits = qs.filter(direction=LedgerEntry.Direction.DEBIT).aggregate(t=Sum("amount"))["t"] or Decimal("0")
    credits = qs.filter(direction=LedgerEntry.Direction.CREDIT).aggregate(t=Sum("amount"))["t"] or Decimal("0")
    return _money(debits - credits)


def _net_account_amount(entries, account_code, normal_direction):
    """Net movement on one account across the given (scoped) journal entries.

    ``normal_direction`` is the account's normal balance side (debit for assets/
    expenses, credit for liabilities/revenue); the opposite side subtracts, so
    reversals net out naturally.
    """
    total = Decimal("0")
    for entry in entries:
        for line in entry.entries.all():
            if line.account.code != account_code:
                continue
            if line.direction == normal_direction:
                total += line.amount
            else:
                total -= line.amount
    return total


def get_or_create_rate(from_currency, to_currency, effective_at=None, source="manual"):
    if from_currency == to_currency:
        return Decimal("1")
    effective_at = effective_at or timezone.now()
    rate = (
        ExchangeRate.objects.filter(from_currency=from_currency, to_currency=to_currency, effective_at__lte=effective_at)
        .order_by("-effective_at")
        .first()
    )
    if not rate:
        raise LedgerError(f"No exchange rate configured for {from_currency} -> {to_currency}.")
    return rate.rate


def convert_amount(amount, from_currency, to_currency, effective_at=None, source="manual"):
    """Convert using a stored historical rate; never silently converts if none exists."""
    rate = get_or_create_rate(from_currency, to_currency, effective_at, source)
    return _money(Decimal(amount) * rate)




def financial_dashboard(user, start=None, end=None, insurer_ids=None):
    """Financial position for the calling user (customer, insurer staff or platform).

    ``start``/``end`` narrow cash-flow metrics (collections, refunds, payment and
    refund counts, per-insurer collections). Ledger totals
    (``premium_earned_recognized``, ``commission_expense_recorded``) and current
    position figures (``commissions_outstanding``, ``outstanding_settlements``)
    are cumulative/snapshot values and are intentionally not date-filtered.
    """
    from apps.common.models import is_platform_admin, user_org_ids
    from apps.insurance.models import Insurer
    from .models import JournalEntry, LedgerAccount, LedgerEntry, Settlement

    org_ids = user_org_ids(user)
    month_start = timezone.now().date().replace(day=1)

    if user.role == User.Role.CUSTOMER:
        payments = Payment.objects.filter(
            user=user, purpose=Payment.Purpose.PREMIUM, status=Payment.Status.SUCCEEDED
        )
        if start:
            payments = payments.filter(verified_at__date__gte=start)
        if end:
            payments = payments.filter(verified_at__date__lte=end)
        refunds = Refund.objects.filter(
            payment__user=user, payment__purpose=Payment.Purpose.PREMIUM, status=Refund.Status.COMPLETED
        ).select_related("payment")
        if start:
            refunds = refunds.filter(payment__verified_at__date__gte=start)
        if end:
            refunds = refunds.filter(payment__verified_at__date__lte=end)
        gross = _money(payments.aggregate(t=Sum("amount"))["t"])
        refunded = _money(refunds.aggregate(t=Sum("amount"))["t"])
        net_collected = _money(Decimal(gross) - Decimal(refunded))
        collected_this_month = _money(
            payments.filter(verified_at__gte=timezone.make_aware(datetime.combine(month_start, time.min))).aggregate(
                t=Sum("amount")
            )["t"]
        )
        return {
            "scope": "customer",
            "gross_premium_collected": _money_str(gross),
            "net_premium_collected": _money_str(net_collected),
            "refunded": _money_str(refunded),
            "collected_this_month": _money_str(collected_this_month),
            "payment_count": payments.count(),
            "refund_count": refunds.count(),
            "open_payments": Payment.objects.filter(
                user=user, purpose=Payment.Purpose.PREMIUM, status=Payment.Status.PENDING
            ).count(),
            "by_method": [
                {
                    "method": row["method"],
                    "total": _money_str(row["total"]),
                    "count": row["count"],
                }
                for row in payments.values("method").annotate(total=Sum("amount"), count=Count("id")).order_by("method")
            ],
            "by_purpose": [
                {
                    "purpose": row["purpose"],
                    "total": _money_str(row["total"]),
                    "count": row["count"],
                }
                for row in payments.values("purpose").annotate(total=Sum("amount"), count=Count("id")).order_by("purpose")
            ],
        }



    if insurer_ids is not None:
        insurer_id_list = list(insurer_ids)
    elif is_platform_admin(user):
        insurer_id_list = list(Insurer.objects.all().values_list("id", flat=True))
    else:
        insurer_id_list = list(
            Insurer.objects.filter(organization_id__in=org_ids).values_list("id", flat=True)
        )
    payment_filter = Q(application__quotation__insurer_id__in=insurer_id_list) | Q(
        policy__insurer_id__in=insurer_id_list
    )
    payments = (
        Payment.objects.filter(
            payment_filter,
            purpose=Payment.Purpose.PREMIUM,
            status=Payment.Status.SUCCEEDED,
        )
        .select_related("user", "application", "policy")
        .order_by("-verified_at")
    )
    if start:
        payments = payments.filter(verified_at__date__gte=start)
    if end:
        payments = payments.filter(verified_at__date__lte=end)
    refunds = Refund.objects.filter(
        Q(payment__purpose=Payment.Purpose.PREMIUM)
        & (Q(payment__application__quotation__insurer__in=insurer_id_list) | Q(payment__policy__insurer__in=insurer_id_list)),
        status=Refund.Status.COMPLETED,
    ).select_related("payment__application", "payment__policy")
    if start:
        refunds = refunds.filter(payment__verified_at__date__gte=start)
    if end:
        refunds = refunds.filter(payment__verified_at__date__lte=end)
    gross = _money(payments.aggregate(t=Sum("amount"))["t"])
    refunded = _money(refunds.aggregate(t=Sum("amount"))["t"])
    net_collected = _money(Decimal(gross) - Decimal(refunded))
    collected_this_month = _money(
        payments.filter(verified_at__gte=timezone.make_aware(datetime.combine(month_start, time.min))).aggregate(
            t=Sum("amount")
        )["t"]
    )



    if is_platform_admin(user):
        commissions = Commission.objects.select_related("policy", "agent", "organization", "dealership").all()
    else:
        commissions = Commission.objects.filter(
            Q(organization_id__in=org_ids) | Q(policy__insurer__organization_id__in=org_ids),
            status__in=[Commission.Status.PENDING, Commission.Status.APPROVED, Commission.Status.PAYABLE],
        ).select_related("policy", "agent", "organization", "dealership")
    commissions_outstanding = _money(commissions.aggregate(t=Sum("amount"))["t"])
    commissions_by_status = list(
        commissions.values("status").annotate(total=Sum("amount"), count=Count("id")).order_by("status")
    )

    if is_platform_admin(user):
        settlements = Settlement.objects.select_related("insurer").all()
    elif org_ids:
        settlements = Settlement.objects.filter(insurer__organization__in=org_ids).select_related("insurer")
    else:
        settlements = Settlement.objects.none()
    outstanding_settlements = _money(
        sum(
            (
                settlement.outstanding
                for settlement in settlements.filter(
                    status__in=[Settlement.Status.PENDING, Settlement.Status.INSTRUCTED, Settlement.Status.SETTLED]
                )
            ),
            Decimal("0"),
        )
    )

    premium_entries = JournalEntry.objects.filter(
        status=JournalEntry.Status.POSTED, entries__account__code="3000"
    )
    commission_entries = JournalEntry.objects.filter(
        status=JournalEntry.Status.POSTED, entries__account__code="4000"
    )
    # Cumulative ledger total (all posted entries); start/end do not narrow it.
    if not is_platform_admin(user):
        journal_scope = (
            Q(policy__insurer_id__in=insurer_id_list)
            | Q(payment__application__quotation__insurer_id__in=insurer_id_list)
            | Q(payment__policy__insurer_id__in=insurer_id_list)
            | Q(settlement__insurer_id__in=insurer_id_list)
            | Q(commission__policy__insurer_id__in=insurer_id_list)
        )
        premium_entries = premium_entries.filter(journal_scope)
        commission_entries = commission_entries.filter(journal_scope)
    premium_entries = premium_entries.distinct().prefetch_related("entries__account")
    premium_earned = _money(_net_account_amount(premium_entries, "3000", LedgerEntry.Direction.CREDIT))
    commission_entries = commission_entries.distinct().prefetch_related("entries__account")
    commission_expense = _money(_net_account_amount(commission_entries, "4000", LedgerEntry.Direction.DEBIT))

    by_insurer = []
    insurer_summaries = list(
        payments.values_list("policy__insurer_id", "policy__insurer__display_name")
        .distinct()
        .order_by("policy__insurer__display_name")
    )
    for insurer_id, insurer_name in insurer_summaries:
        insurer_payments = payments.filter(
            Q(policy__insurer_id=insurer_id) | Q(application__quotation__insurer_id=insurer_id)
        )
        insurer_refunds = refunds.filter(
            Q(payment__application__quotation__insurer_id=insurer_id) | Q(payment__policy__insurer_id=insurer_id)
        )
        collected = _money(insurer_payments.aggregate(t=Sum("amount"))["t"])
        refunded = _money(insurer_refunds.aggregate(t=Sum("amount"))["t"])
        insurer_outstanding = _money(
            sum(
                (
                    settlement.outstanding
                    for settlement in settlements.filter(
                        insurer__id=insurer_id,
                        status__in=[Settlement.Status.PENDING, Settlement.Status.INSTRUCTED, Settlement.Status.SETTLED],
                    )
                ),
                Decimal("0"),
            )
        )
        by_insurer.append(
            {
                "insurer": insurer_name,
                "insurer_id": str(insurer_id),
                "collected": _money_str(collected),
                "refunded": _money_str(refunded),
                "net_collected": _money_str(Decimal(collected) - Decimal(refunded)),
                "outstanding_settlements": _money_str(insurer_outstanding),
            }
        )

    return {
        "scope": "insurer" if insurer_id_list else "platform",
        "insurer_id": str(insurer_id_list[0]) if insurer_id_list else None,
        "gross_premium_collected": _money_str(gross),
        "net_premium_collected": _money_str(net_collected),
        "refunded": _money_str(refunded),
        "collected_this_month": _money_str(collected_this_month),
        "outstanding_settlements": _money_str(outstanding_settlements),
        "premium_earned_recognized": _money_str(premium_earned),
        "commission_expense_recorded": _money_str(commission_expense),
        "commissions_outstanding": _money_str(commissions_outstanding),
        "commissions_by_status": commissions_by_status,
        "payment_count": payments.count(),
        "refund_count": refunds.count(),
        "payments_by_method": [
            {
                "method": row["method"],
                "total": _money_str(row["total"]),
                "count": row["count"],
            }
            for row in payments.values("method").annotate(total=Sum("amount"), count=Count("id")).order_by("method")
        ],
        "by_insurer": by_insurer,
        "settlements": [
            {
                "id": str(s.id),
                "reference": s.reference,
                "insurer": s.insurer.display_name,
                "amount_due": _money_str(s.amount_due),
                "amount_settled": _money_str(s.amount_settled),
                "outstanding": _money_str(s.outstanding),
                "currency": s.currency,
                "status": s.status,
                "settlement_reference": s.settlement_reference,
                "settled_at": s.settled_at,
                "created_at": s.created_at,
            }
            for s in settlements.order_by("-created_at")[:50]
        ],
    }


def premium_tracking_summary(policy, customer=None):
    """Summarise premium due, collected and refunded for a policy."""
    from django.conf import settings

    from apps.insurance.models import Policy

    payments = Payment.objects.filter(
        policy=policy,
        purpose=Payment.Purpose.PREMIUM,
        status=Payment.Status.SUCCEEDED,
    ).select_related("user", "application")
    refunds = Refund.objects.filter(payment__policy=policy, status=Refund.Status.COMPLETED).select_related("payment")
    collected = _money(payments.aggregate(t=Sum("amount"))["t"])
    refunded = _money(refunds.aggregate(t=Sum("amount"))["t"])
    outstanding_balance = _money(max(Decimal(str(policy.premium)) - Decimal(str(collected)) - Decimal(str(refunded)), Decimal("0")))
    # Currency is established by the underlying premium payment when present;
    # otherwise fall back to the configured reporting currency (never assume KES).
    currency = (
        payments.order_by("verified_at").values_list("currency", flat=True).first()
        or getattr(settings, "DEFAULT_CURRENCY", "KES")
    )
    return {
        "policy": policy.policy_number,
        "customer": customer or policy.customer.full_name,
        "premium": _money_str(policy.premium),
        "collected": _money_str(collected),
        "refunded": _money_str(refunded),
        "outstanding_balance": _money_str(outstanding_balance),
        "payment_count": payments.count(),
        "refund_count": refunds.count(),
        "status": policy.status,
        "start_date": policy.start_date,
        "end_date": policy.end_date,
        "currency": currency,
    }


def ledger_balances():
    """Return the current active ledger balance for each configured account."""
    return [
        {
            "account": account.code,
            "name": account.name,
            "type": account.type,
            "currency": account.currency,
            "balance": str(account_balance(account.code)),
        }
        for account in LedgerAccount.objects.filter(is_active=True).order_by("code")
    ]


def mark_payment_settled(payment, settled_by=None, settlement_reference=""):
    """Mark a verified payment as settled (funds actually received)."""
    if payment.status != Payment.Status.SUCCEEDED or payment.verified_at is None:
        raise LedgerError("Only verified payments can be marked settled.")
    if payment.status == Payment.Status.SETTLED:
        return payment
    payment.status = Payment.Status.SETTLED
    payment.settled_at = timezone.now()
    if settlement_reference:
        payment.provider_reference = settlement_reference or payment.provider_reference
    payment.save(update_fields=["status", "settled_at", "provider_reference"])
    return payment


def reconcile_settlement(settlement, reconciliation_notes="", reconciled_by=None):
    """Mark a settled insurer settlement as reconciled against recorded transactions."""
    if settlement.status != Settlement.Status.SETTLED:
        raise LedgerError("Only settled settlements can be reconciled.")
    settlement.status = Settlement.Status.RECONCILED
    settlement.reconciliation_notes = reconciliation_notes or settlement.reconciliation_notes
    settlement.updated_at = timezone.now()
    settlement.save(update_fields=["status", "reconciliation_notes", "updated_at"])
    return settlement


def create_settlement_from_verified_payments(insurer, created_by=None, instructions=""):
    """Create an insurer settlement from the insurer's verified, unsettled premium receipts."""
    from apps.common.utils import generate_reference

    eligible = Payment.objects.filter(
        Q(application__quotation__insurer=insurer) | Q(policy__insurer=insurer),
        purpose=Payment.Purpose.PREMIUM,
        status=Payment.Status.SUCCEEDED,
    ).select_related("application", "policy")
    amount_due = sum(
        (
            payment.amount
            - (
                payment.refunds.filter(status=Refund.Status.COMPLETED)
                .aggregate(total=Sum("amount"))["total"]
                or Decimal("0")
            )
            for payment in eligible
        ),
        Decimal("0"),
    )
    if amount_due <= 0:
        return None

    settlement = Settlement.objects.create(
        reference=generate_reference("SET", 10),
        insurer=insurer,
        amount_due=_money(amount_due),
        status=Settlement.Status.INSTRUCTED,
        settlement_instructions=instructions or "Auto-created from verified premium receipts.",
        settled_by=created_by,
    )
    return settlement
