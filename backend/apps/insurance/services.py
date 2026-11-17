"""Insurance domain services: numbering, quotation engine, policy issuance."""
import json
import textwrap
from decimal import ROUND_HALF_UP, Decimal

from django.core.files.base import ContentFile
from django.db import transaction
from django.utils import timezone

from apps.common.utils import generate_reference
from apps.organizations.models import Organization
from apps.payments.models import Payment

from .models import Application, Insurer, Policy, Product, Quotation, QuotationRequest

USAGE_SURCHARGE = {
    "private": Decimal("0.00"),
    "commercial": Decimal("0.15"),
    "psv": Decimal("0.35"),
}


def _money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def compute_premium(product: Product, sum_insured: Decimal, usage: str = "private") -> Decimal:
    """Premium derived from the insurer's published rate for this product.

    This is the platform's normalized pricing engine, not a fabricated provider
    response. It is labelled `internal` on the resulting quotation.
    """
    base = sum_insured * (product.base_premium_rate / Decimal("100"))
    surcharge = base * USAGE_SURCHARGE.get(usage, Decimal("0.00"))
    total = base + surcharge
    return _money(max(total, product.minimum_premium))


@transaction.atomic
def generate_quotes(request: QuotationRequest, insurer_ids=None) -> list[Quotation]:
    products = (
        Product.objects.alive()
        .filter(
            is_active=True,
            category=request.coverage_type,
            insurer__is_active=True,
            insurer__organization__status=Organization.Status.VERIFIED,
        )
        .select_related("insurer", "insurer__organization")
    )
    if insurer_ids:
        products = products.filter(insurer_id__in=insurer_ids)
    if request.product_id:
        products = products.filter(id=request.product_id)
    vehicle = request.vehicle
    sum_insured = Decimal(str(request.sum_insured))
    created = []
    for product in products:
        if not product.supports_vehicle(vehicle, sum_insured):
            continue
        premium = compute_premium(product, sum_insured, vehicle.usage)
        quotation, _ = Quotation.objects.get_or_create(
            request=request,
            insurer=product.insurer,
            product=product,
            defaults={
                "quotation_number": generate_reference("QT", 10),
                "sum_insured": sum_insured,
                "premium": premium,
                "excess_amount": product.excess_amount,
                "benefits": product.benefits,
                "exclusions": product.exclusions,
                "terms": product.terms,
                "valid_until": timezone.now() + timezone.timedelta(days=14),
                "source": Quotation.Source.INTERNAL,
            },
        )
        created.append(quotation)
    if created:
        request.status = QuotationRequest.Status.QUOTED
        request.save(update_fields=["status"])
    return created


@transaction.atomic
def select_quotation(quotation: Quotation) -> Quotation:
    request = quotation.request
    Quotation.objects.filter(request=request).exclude(pk=quotation.pk).update(status=Quotation.Status.REJECTED)
    quotation.status = Quotation.Status.SELECTED
    quotation.save(update_fields=["status"])
    request.status = QuotationRequest.Status.SELECTED
    request.save(update_fields=["status"])
    return quotation


@transaction.atomic
def _pdf_escape(value):
    return str(value).replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def build_policy_document(policy: Policy) -> bytes:
    """Build a self-contained one-page PDF certificate using only the standard library."""
    quotation = policy.application.quotation
    lines = [
        "INSURECONNECT POLICY CERTIFICATE",
        "",
        f"Policy reference: {policy.policy_number}",
        f"Provider reference: {policy.provider_reference or policy.insurer.display_name}",
        f"Insurer: {policy.insurer.display_name}",
        f"Product: {policy.product.name}",
        f"Policyholder: {policy.customer.full_name}",
        f"Vehicle: {policy.vehicle.registration_number} - {policy.vehicle.make} {policy.vehicle.model}",
        f"Policy period: {policy.start_date:%d %b %Y} to {policy.end_date:%d %b %Y}",
        f"Premium: KES {policy.premium:,.2f}",
        f"Sum insured: KES {policy.sum_insured:,.2f}",
        f"Excess: KES {policy.excess_amount:,.2f}",
        "",
        f"Coverage: {quotation.request.coverage_type or policy.product.category}",
        f"Quotation reference: {quotation.request.request_number}",
        "",
        "This certificate is issued by the insurer named above through the",
        "INSURECONNECT platform. It is valid subject to the policy terms and",
        "the insurer's underwriting conditions. Verify authenticity with the",
        "insurer using the policy reference shown above.",
    ]
    if quotation.coverage_limits:
        lines.extend(["", f"Coverage limits: {json.dumps(quotation.coverage_limits)}"])
    if quotation.deductibles:
        lines.extend([f"Deductibles: {json.dumps(quotation.deductibles)}"])
    if quotation.exclusions:
        lines.extend(["", "Exclusions:"])
        lines.extend(textwrap.wrap(json.dumps(quotation.exclusions), width=86))

    content = ["BT", "/F1 16 Tf", "50 790 Td", "16 TL"]
    for index, line in enumerate(lines):
        wrapped = [line] if not line else textwrap.wrap(line, width=86) or [""]
        for part in wrapped:
            size = 16 if index == 0 else 10
            content.append(f"/F1 {size} Tf")
            content.append(f"({_pdf_escape(part)}) Tj")
            content.append("T*")
    content.append("ET")
    stream = "\n".join(content).encode("latin-1", "replace")

    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
        b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length " + str(len(stream)).encode("ascii") + b" >>\nstream\n" + stream + b"\nendstream",
    ]

    pdf = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]
    for number, body in enumerate(objects, start=1):
        offsets.append(len(pdf))
        pdf.extend(f"{number} 0 obj\n".encode("ascii"))
        pdf.extend(body)
        pdf.extend(b"\nendobj\n")
    xref_at = len(pdf)
    pdf.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    pdf.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        pdf.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    pdf.extend(
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_at}\n%%EOF\n".encode("ascii")
    )
    return bytes(pdf)


def issue_policy(
    application: Application,
    issued_by,
    start_date=None,
    end_date=None,
    provider_reference="",
    generate_document=True,
) -> Policy:
    application = Application.objects.select_for_update().get(pk=application.pk)
    if Policy.objects.filter(application=application).exists():
        raise ValueError("Policy already issued for this application.")
    quotation = application.quotation
    product = quotation.product
    start = start_date or timezone.now().date()
    end = end_date or (start.replace(year=start.year + 1) - timezone.timedelta(days=1))
    policy = Policy.objects.create(
        policy_number=generate_reference(f"POL-{product.code[:6]}", 8),
        application=application,
        customer=application.customer,
        insurer=quotation.insurer,
        product=product,
        vehicle=application.vehicle,
        start_date=start,
        end_date=end,
        premium=quotation.premium,
        sum_insured=quotation.sum_insured,
        excess_amount=quotation.excess_amount,
        status=Policy.Status.ACTIVE,
        issued_at=timezone.now(),
        provider_reference=provider_reference,
    )
    application.status = Application.Status.POLICY_ISSUED
    application.reviewed_by = issued_by
    application.save(update_fields=["status", "reviewed_by"])
    # Double-entry ledger: premium is earned when the policy is issued.
    premium = quotation.premium
    premium_payment = (
        application.payments.filter(purpose=Payment.Purpose.PREMIUM, status=Payment.Status.SUCCEEDED)
        .order_by("-verified_at")
        .first()
    )
    from apps.finance.services import post_journal_entry

    post_journal_entry(
        reference=f"POL-{policy.policy_number}",
        description=f"Premium earned on policy issuance {policy.policy_number}",
        lines=[
            {"account": "2000", "direction": "debit", "amount": premium, "reference": policy.policy_number},
            {"account": "3000", "direction": "credit", "amount": premium, "reference": policy.policy_number},
        ],
        currency=premium_payment.currency if premium_payment else "KES",
        posted_by=issued_by,
        policy=policy,
    )
    if generate_document:
        pdf = build_policy_document(policy)
        policy.certificate.save(f"{policy.policy_number}.pdf", ContentFile(pdf), save=True)
    _create_agent_commission(policy, application)
    _create_dealer_commission(policy, application)
    return policy


def _create_dealer_commission(policy, application):
    """Auto-create a dealer referral commission when an application originated from a dealership."""
    if not application.dealership_id or not application.partnership_id:
        return
    from apps.business_network.services import compute_dealer_commission
    from apps.payments.models import Commission

    rate, amount = compute_dealer_commission(application.partnership, policy.product, policy.premium)
    if amount <= 0:
        return
    commission = Commission.objects.create(
        policy=policy,
        dealership_id=application.dealership_id,
        organization=policy.insurer.organization,
        rate=rate,
        amount=amount,
    )
    _post_commission_ledger(commission, "KES")
    return commission


def _create_agent_commission(policy, application):
    """Auto-create a commission when an application was attributed to an agent."""
    if not application.agent_id:
        return
    from apps.accounts.models import AgentProfile
    from apps.payments.models import Commission

    profile = AgentProfile.objects.filter(user_id=application.agent_id).first()
    rate = profile.commission_rate if profile else Decimal("10.00")
    amount = (policy.premium * rate / Decimal("100")).quantize(Decimal("0.01"))
    commission = Commission.objects.create(
        policy=policy,
        agent_id=application.agent_id,
        organization=policy.insurer.organization,
        rate=rate,
        amount=amount,
    )
    _post_commission_ledger(commission, "KES")
    return commission


def _post_commission_ledger(commission, currency):
    from apps.finance.services import post_journal_entry

    post_journal_entry(
        reference=f"COM-{commission.id}",
        description=f"Commission payable for policy {commission.policy.policy_number}",
        lines=[
            {"account": "4000", "direction": "debit", "amount": commission.amount, "reference": str(commission.id)},
            {"account": "5000", "direction": "credit", "amount": commission.amount, "reference": str(commission.id)},
        ],
        currency=currency,
        posted_by=None,
        commission=commission,
    )



def insurer_for_user(user):
    from apps.organizations.models import Membership

    org_ids = Membership.objects.filter(user=user, is_active=True).values_list("organization_id", flat=True)
    return Insurer.objects.filter(organization_id__in=org_ids).first()
