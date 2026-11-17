from django.db import transaction
from django.utils import timezone

from .models import Claim, ClaimStatusHistory

TRANSITIONS = {
    Claim.Status.DRAFT: {Claim.Status.SUBMITTED, Claim.Status.WITHDRAWN},
    Claim.Status.SUBMITTED: {Claim.Status.UNDER_REVIEW, Claim.Status.WITHDRAWN, Claim.Status.REJECTED},
    Claim.Status.UNDER_REVIEW: {Claim.Status.INFO_REQUIRED, Claim.Status.INSPECTION_SCHEDULED, Claim.Status.ASSESSMENT, Claim.Status.APPROVED, Claim.Status.REJECTED},
    Claim.Status.INFO_REQUIRED: {Claim.Status.UNDER_REVIEW, Claim.Status.REJECTED, Claim.Status.WITHDRAWN},
    Claim.Status.INSPECTION_SCHEDULED: {Claim.Status.ASSESSMENT, Claim.Status.UNDER_REVIEW, Claim.Status.REJECTED},
    Claim.Status.ASSESSMENT: {Claim.Status.APPROVED, Claim.Status.REJECTED, Claim.Status.INFO_REQUIRED},
    Claim.Status.APPROVED: {Claim.Status.SETTLED, Claim.Status.CLOSED},
    Claim.Status.REJECTED: {Claim.Status.CLOSED},
    Claim.Status.SETTLED: {Claim.Status.CLOSED},
    Claim.Status.CLOSED: set(),
    Claim.Status.WITHDRAWN: set(),
}


def can_transition(current, target):
    return target in TRANSITIONS.get(current, set())


@transaction.atomic
def transition(claim, target, actor, notes=""):
    if not can_transition(claim.status, target):
        raise ValueError(f"Cannot transition claim from {claim.status} to {target}.")
    old = claim.status
    claim.status = target
    if target == Claim.Status.SETTLED:
        claim.settled_at = timezone.now()
    if target == Claim.Status.CLOSED:
        claim.closed_at = timezone.now()
    claim.save()
    ClaimStatusHistory.objects.create(
        claim=claim, from_status=old, to_status=target, changed_by=actor, notes=notes
    )
    return claim
