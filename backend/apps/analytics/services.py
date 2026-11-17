from datetime import timedelta
from decimal import Decimal

from django.db.models import Count, Q, Sum
from django.db.models.functions import TruncMonth
from django.utils import timezone

from apps.accounts.models import User
from apps.claims.models import Claim
from apps.insurance.models import Application, Insurer, Policy, Product, Quotation, QuotationRequest
from apps.inspections.models import Inspection
from apps.organizations.models import Organization
from apps.payments.models import Commission, Payment


def _money(value):
    return str((value or Decimal("0")).quantize(Decimal("0.01")))


def customer_dashboard(user):
    today = timezone.now().date()
    soon = today + timedelta(days=30)
    return {
        "vehicles": user.vehicles.alive().count(),
        "quotation_requests": QuotationRequest.objects.filter(customer=user).count(),
        "open_quotation_requests": QuotationRequest.objects.filter(
            customer=user, status__in=["pending", "quoted", "selected"]
        ).count(),
        "applications": Application.objects.filter(customer=user).count(),
        "applications_pending": Application.objects.filter(
            customer=user,
            status__in=["submitted", "under_review", "more_info", "approved"],
        ).count(),
        "active_policies": Policy.objects.filter(customer=user, status=Policy.Status.ACTIVE).count(),
        "policies_expiring_soon": Policy.objects.filter(
            customer=user, status=Policy.Status.ACTIVE, end_date__lte=soon, end_date__gte=today
        ).count(),
        "open_claims": Claim.objects.filter(customer=user)
        .exclude(status__in=["closed", "settled", "withdrawn", "rejected"])
        .count(),
        "unpaid_approved_applications": Application.objects.filter(
            customer=user, status__in=["approved", "under_review", "submitted"]
        )
        .exclude(payments__status=Payment.Status.SUCCEEDED, payments__purpose=Payment.Purpose.PREMIUM)
        .distinct()
        .count(),
        "unread_notifications": user.notifications.filter(is_read=False).count(),
        "total_paid": _money(
            Payment.objects.filter(user=user, status=Payment.Status.SUCCEEDED).aggregate(t=Sum("amount"))["t"]
        ),
    }


def provider_dashboard(user):
    from apps.common.models import user_org_ids

    org_ids = user_org_ids(user)
    insurer_ids = list(Insurer.objects.filter(organization_id__in=org_ids).values_list("id", flat=True))
    today = timezone.now().date()
    soon = today + timedelta(days=30)
    open_requests = QuotationRequest.objects.filter(status__in=["pending", "quoted", "selected"])
    if insurer_ids:
        open_requests = open_requests.filter(
            Q(insurer_id__in=insurer_ids)
            | Q(insurer__isnull=True, dealership__isnull=True)
            | Q(quotations__insurer_id__in=insurer_ids)
        ).distinct()
    else:
        open_requests = open_requests.filter(insurer__isnull=True, dealership__isnull=True)
    return {
        "products": Product.objects.alive().filter(insurer_id__in=insurer_ids).count(),
        "active_products": Product.objects.alive().filter(insurer_id__in=insurer_ids, is_active=True).count(),
        "open_quotation_requests": open_requests.count(),
        "quotations_sent": Quotation.objects.filter(insurer_id__in=insurer_ids).count(),
        "applications_received": Application.objects.filter(
            quotation__insurer_id__in=insurer_ids
        ).count(),
        "applications_pending": Application.objects.filter(
            quotation__insurer_id__in=insurer_ids,
            status__in=["submitted", "under_review", "more_info", "approved"],
        ).count(),
        "active_policies": Policy.objects.filter(
            insurer_id__in=insurer_ids, status=Policy.Status.ACTIVE
        ).count(),
        "policies_expiring_soon": Policy.objects.filter(
            insurer_id__in=insurer_ids, status=Policy.Status.ACTIVE, end_date__lte=soon, end_date__gte=today
        ).count(),
        "open_claims": Claim.objects.filter(policy__insurer_id__in=insurer_ids)
        .exclude(status__in=["closed", "settled", "withdrawn", "rejected"])
        .count(),
        "claims_requiring_action": Claim.objects.filter(
            policy__insurer_id__in=insurer_ids, status__in=["submitted", "under_review", "info_required", "assessment"]
        ).count(),
        "payments_awaiting_verification": Payment.objects.filter(
            Q(application__quotation__insurer_id__in=insurer_ids) | Q(policy__insurer_id__in=insurer_ids),
            status__in=[Payment.Status.PENDING, Payment.Status.PROCESSING],
        ).count(),
        "premium_collected": _money(
            Payment.objects.filter(
                Q(application__quotation__insurer_id__in=insurer_ids) | Q(policy__insurer_id__in=insurer_ids),
                purpose=Payment.Purpose.PREMIUM,
                status=Payment.Status.SUCCEEDED,
            ).aggregate(t=Sum("amount"))["t"]
        ),
        "commissions_pending": _money(
            Commission.objects.filter(
                organization_id__in=org_ids, status=Commission.Status.PENDING
            ).aggregate(t=Sum("amount"))["t"]
        ),
        "inspections_scheduled": Inspection.objects.filter(
            organization_id__in=org_ids, status__in=["scheduled", "in_progress"]
        ).count(),
    }


def admin_dashboard():
    today = timezone.now().date()
    soon = today + timedelta(days=30)
    month_start = today.replace(day=1)
    succeeded = Payment.objects.filter(status=Payment.Status.SUCCEEDED)
    return {
        "users": {
            "total": User.objects.count(),
            "customers": User.objects.filter(role=User.Role.CUSTOMER).count(),
            "providers": User.objects.filter(
                role__in=[User.Role.PROVIDER_ADMIN, User.Role.PROVIDER_STAFF]
            ).count(),
            "agents": User.objects.filter(role=User.Role.AGENT).count(),
            "inspectors": User.objects.filter(role=User.Role.INSPECTOR).count(),
            "claims_officers": User.objects.filter(role=User.Role.CLAIMS_OFFICER).count(),
            "unverified_email": User.objects.filter(email_verified=False).count(),
        },
        "organizations": {
            "total": Organization.objects.count(),
            "pending": Organization.objects.filter(status=Organization.Status.PENDING).count(),
            "verified": Organization.objects.filter(status=Organization.Status.VERIFIED).count(),
            "suspended": Organization.objects.filter(status=Organization.Status.SUSPENDED).count(),
        },
        "catalogue": {
            "insurers": Insurer.objects.count(),
            "products": Product.objects.alive().count(),
            "active_products": Product.objects.alive().filter(is_active=True).count(),
        },
        "marketplace": {
            "quotation_requests": QuotationRequest.objects.count(),
            "quotations": Quotation.objects.count(),
            "applications": Application.objects.count(),
            "applications_pending": Application.objects.filter(
                status__in=["submitted", "under_review", "more_info", "approved"]
            ).count(),
            "policies": Policy.objects.count(),
            "active_policies": Policy.objects.filter(status=Policy.Status.ACTIVE).count(),
            "expiring_soon": Policy.objects.filter(
                status=Policy.Status.ACTIVE, end_date__lte=soon, end_date__gte=today
            ).count(),
        },
        "claims": {
            "total": Claim.objects.count(),
            "open": Claim.objects.exclude(status__in=["closed", "settled", "withdrawn", "rejected"]).count(),
            "pending_review": Claim.objects.filter(status__in=["submitted", "under_review"]).count(),
            "settled_amount": _money(Claim.objects.aggregate(t=Sum("settled_amount"))["t"]),
        },
        "inspections": {
            "total": Inspection.objects.count(),
            "scheduled": Inspection.objects.filter(status__in=["scheduled", "in_progress"]).count(),
            "completed": Inspection.objects.filter(status=Inspection.Status.COMPLETED).count(),
        },
        "finance": {
            "gross_collected": _money(succeeded.aggregate(t=Sum("amount"))["t"]),
            "collected_this_month": _money(
                succeeded.filter(verified_at__date__gte=month_start).aggregate(t=Sum("amount"))["t"]
            ),
            "pending_verification": Payment.objects.filter(
                status__in=[Payment.Status.PENDING, Payment.Status.PROCESSING]
            ).count(),
            "refunded": _money(
                Payment.objects.filter(status=Payment.Status.REFUNDED).aggregate(t=Sum("amount"))["t"]
            ),
            "commissions_pending": _money(
                Commission.objects.filter(status=Commission.Status.PENDING).aggregate(t=Sum("amount"))["t"]
            ),
        },
        "provider_performance": [
            {
                "insurer": row["insurer__display_name"],
                "quotations": row["count"],
                "premium": _money(row["premium"]),
            }
            for row in Quotation.objects.values("insurer__display_name")
            .annotate(count=Count("id"), premium=Sum("premium"))
            .order_by("-count")[:10]
        ],
        "policies_by_status": list(
            Policy.objects.values("status").annotate(count=Count("id")).order_by("status")
        ),
        "claims_by_status": list(
            Claim.objects.values("status").annotate(count=Count("id")).order_by("status")
        ),
        "revenue_by_month": list(
            succeeded.annotate(month=TruncMonth("verified_at"))
            .values("month")
            .annotate(total=Sum("amount"), count=Count("id"))
            .order_by("month")[:12]
        )
        if succeeded.exists()
        else [],
    }


def financial_report(start=None, end=None, insurer_ids=None):
    qs = Payment.objects.filter(status=Payment.Status.SUCCEEDED)
    if insurer_ids is not None:
        qs = qs.filter(
            Q(application__quotation__insurer_id__in=insurer_ids) | Q(policy__insurer_id__in=insurer_ids)
        )
    if start:
        qs = qs.filter(verified_at__date__gte=start)
    if end:
        qs = qs.filter(verified_at__date__lte=end)
    by_method = list(qs.values("method").annotate(total=Sum("amount"), count=Count("id")).order_by("method"))
    by_purpose = list(qs.values("purpose").annotate(total=Sum("amount"), count=Count("id")).order_by("purpose"))
    return {
        "total": _money(qs.aggregate(t=Sum("amount"))["t"]),
        "count": qs.count(),
        "by_method": [{"method": r["method"], "total": _money(r["total"]), "count": r["count"]} for r in by_method],
        "by_purpose": [{"purpose": r["purpose"], "total": _money(r["total"]), "count": r["count"]} for r in by_purpose],
    }
