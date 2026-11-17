"""Reusable tenant-scoping helpers to avoid duplicated authorization queries."""
from .models import is_platform_admin, user_org_ids


def user_insurer_ids(user):
    """Insurer ids the user belongs to (empty for customers / anonymous)."""
    if not user or not user.is_authenticated:
        return []
    from apps.insurance.models import Insurer

    return list(
        Insurer.objects.filter(organization_id__in=user_org_ids(user)).values_list("id", flat=True)
    )


def insurer_ids_for(user):
    """Insurer ids a provider user may act on; None means unrestricted (admin)."""
    if is_platform_admin(user):
        return None
    return user_insurer_ids(user)
