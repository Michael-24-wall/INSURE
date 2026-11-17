"""Business network domain services: partnerships, consent, commissions."""
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from apps.insurance.models import Insurer
from apps.notifications.services import notify
from apps.organizations.models import Membership, Organization

from .models import (
    CustomerConsent,
    Partnership,
    PartnershipActivity,
    PartnershipCommissionTerms,
    PartnershipRequest,
)


def user_dealer_org(user):
    """Return the dealer Organization the user belongs to, or None."""
    if not user or not user.is_authenticated:
        return None
    membership = (
        Membership.objects.filter(
            user=user, is_active=True, organization__organization_type=Organization.Type.DEALER
        )
        .select_related("organization")
        .first()
    )
    return membership.organization if membership else None


def user_insurer(user):
    """Return the Insurer the user belongs to, or None."""
    if not user or not user.is_authenticated:
        return None
    from apps.common.scoping import user_insurer_ids

    ids = user_insurer_ids(user)
    return Insurer.objects.filter(id__in=ids).first() if ids else None


def org_member_users(organization):
    return list(
        Membership.objects.filter(organization=organization, is_active=True).select_related("user").values_list("user", flat=True)
    )


def notify_org(organization, title, message, category="organization", link=""):
    for uid in org_member_users(organization):
        from apps.accounts.models import User

        user = User.objects.filter(pk=uid).first()
        if user:
            notify(user, title, message, category, link)


def _resolve_parties(a, b):
    """Return (insurer, dealership) regardless of request direction."""
    if a.organization_type == Organization.Type.INSURER:
        insurer = Insurer.objects.filter(organization=a).first()
        dealership = b
    elif b.organization_type == Organization.Type.INSURER:
        insurer = Insurer.objects.filter(organization=b).first()
        dealership = a
    else:
        raise ValueError("A partnership requires one insurer and one dealership.")
    if insurer is None:
        raise ValueError("Insurer profile not found; the insurer must be verified first.")
    return insurer, dealership


def _record(partnership, actor, action, notes=""):
    return PartnershipActivity.objects.create(partnership=partnership, actor=actor, action=action, notes=notes)


@transaction.atomic
def create_partnership_request(from_org, to_org, message="", actor=None):
    if from_org.id == to_org.id:
        raise ValueError("An organization cannot partner with itself.")
    existing = PartnershipRequest.objects.filter(
        from_organization=from_org, to_organization=to_org,
        status__in=[PartnershipRequest.Status.PENDING, PartnershipRequest.Status.UNDER_REVIEW],
    ).exists()
    if existing:
        raise ValueError("A pending partnership request already exists between these organizations.")
    request = PartnershipRequest.objects.create(
        from_organization=from_org, to_organization=to_org, message=message
    )
    notify_org(to_org, "New partnership request", f"{from_org.name} wants to partner with you.", "organization")
    return request


@transaction.atomic
def respond_to_partnership_request(request_obj, action, actor=None, note=""):
    if request_obj.status not in {PartnershipRequest.Status.PENDING, PartnershipRequest.Status.UNDER_REVIEW}:
        raise ValueError("This request has already been responded to.")

    if action == "approve":
        insurer, dealership = _resolve_parties(request_obj.from_organization, request_obj.to_organization)
        partnership, created = Partnership.objects.get_or_create(
            insurer=insurer,
            dealership=dealership,
            defaults={
                "status": Partnership.Status.ACTIVE,
                "effective_date": timezone.now().date(),
                "created_by": actor,
                "approved_by": actor,
                "approved_at": timezone.now(),
            },
        )
        if not created and partnership.status in {Partnership.Status.ACTIVE, Partnership.Status.APPROVED}:
            raise ValueError("An active partnership already exists between these organizations.")
        partnership.status = Partnership.Status.ACTIVE
        partnership.approved_by = actor
        partnership.approved_at = timezone.now()
        if partnership.effective_date is None:
            partnership.effective_date = timezone.now().date()
        partnership.save(update_fields=["status", "approved_by", "approved_at", "effective_date"])
        _record(partnership, actor, "activated", "Partnership approved and activated.")
        request_obj.status = PartnershipRequest.Status.APPROVED
        request_obj.partnership = partnership
        request_obj.responded_by = actor
        request_obj.responded_at = timezone.now()
        request_obj.response_note = note
        request_obj.save()
        notify_org(request_obj.from_organization, "Partnership approved", f"Your partnership with {request_obj.to_organization.name} is now active.", "organization")
        return partnership

    if action == "reject":
        request_obj.status = PartnershipRequest.Status.REJECTED
    elif action == "more_info":
        request_obj.status = PartnershipRequest.Status.MORE_INFO
    else:
        raise ValueError("Invalid action.")

    request_obj.responded_by = actor
    request_obj.responded_at = timezone.now()
    request_obj.response_note = note
    request_obj.save()
    notify_org(request_obj.from_organization, "Partnership request updated", f"{request_obj.to_organization.name} responded to your request.", "organization")
    return request_obj


@transaction.atomic
def suspend_partnership(partnership, actor, reason=""):
    if partnership.status != Partnership.Status.ACTIVE:
        raise ValueError("Only active partnerships can be suspended.")
    partnership.status = Partnership.Status.SUSPENDED
    partnership.suspension_reason = reason
    partnership.save(update_fields=["status", "suspension_reason"])
    _record(partnership, actor, "suspended", reason)
    notify_org(partnership.dealership, "Partnership suspended", reason, "organization")
    return partnership


@transaction.atomic
def reactivate_partnership(partnership, actor):
    if partnership.status != Partnership.Status.SUSPENDED:
        raise ValueError("Only suspended partnerships can be reactivated.")
    partnership.status = Partnership.Status.ACTIVE
    partnership.suspension_reason = ""
    partnership.save(update_fields=["status", "suspension_reason"])
    _record(partnership, actor, "reactivated")
    return partnership


@transaction.atomic
def terminate_partnership(partnership, actor, reason=""):
    if partnership.status not in {Partnership.Status.ACTIVE, Partnership.Status.SUSPENDED, Partnership.Status.APPROVED}:
        raise ValueError("Partnership cannot be terminated in its current state.")
    partnership.status = Partnership.Status.TERMINATED
    partnership.save(update_fields=["status"])
    _record(partnership, actor, "terminated", reason)
    notify_org(partnership.dealership, "Partnership terminated", reason, "organization")
    return partnership


@transaction.atomic
def grant_consent(customer, dealership, insurer, data_categories=None, method=CustomerConsent.Method.DIGITAL):
    consent = CustomerConsent.objects.create(
        customer=customer,
        dealership=dealership,
        insurer=insurer,
        data_categories=data_categories or ["name", "contact", "vehicle"],
        consent_method=method,
        status=CustomerConsent.Status.GRANTED,
    )
    return consent


@transaction.atomic
def withdraw_consent(consent):
    if consent.status != CustomerConsent.Status.GRANTED:
        raise ValueError("Consent is not currently granted.")
    consent.status = CustomerConsent.Status.WITHDRAWN
    consent.withdrawn_at = timezone.now()
    consent.save(update_fields=["status", "withdrawn_at"])
    return consent


def compute_dealer_commission(partnership, product, premium):
    """Return (rate, amount) based on matching commission terms, or (0, 0)."""
    terms = PartnershipCommissionTerms.objects.filter(
        partnership=partnership, status=PartnershipCommissionTerms.Status.ACTIVE
    )
    product_terms = terms.filter(product=product).first() or terms.filter(product__isnull=True).first()
    if not product_terms:
        return Decimal("0"), Decimal("0")
    if product_terms.commission_type == PartnershipCommissionTerms.Type.FIXED:
        return Decimal("0"), product_terms.fixed_amount
    rate = product_terms.rate
    amount = (premium * rate / Decimal("100")).quantize(Decimal("0.01"))
    return rate, amount
