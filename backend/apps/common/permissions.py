from rest_framework.permissions import BasePermission, SAFE_METHODS

from apps.common.models import is_platform_admin, user_org_ids


class IsPlatformAdmin(BasePermission):
    def has_permission(self, request, view):
        return is_platform_admin(request.user)


class IsSuperAdmin(BasePermission):
    def has_permission(self, request, view):
        u = request.user
        return bool(u and u.is_authenticated and (u.is_superuser or u.role == "super_admin"))


class IsCustomer(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.role == "customer")


class IsProviderUser(BasePermission):
    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.role in {"provider_admin", "provider_staff", "agent"}
        )


class IsInspector(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.role == "inspector")


class IsClaimsOfficer(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.role == "claims_officer")


class IsDealerUser(BasePermission):
    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.role in {"dealer_admin", "dealer_staff"}
        )


class IsDealerAdmin(BasePermission):
    def has_permission(self, request, view):
        return bool(
            request.user and request.user.is_authenticated and request.user.role == "dealer_admin"
        )


class IsAdminOrReadOnly(BasePermission):
    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return bool(request.user and request.user.is_authenticated)
        return is_platform_admin(request.user)


class HasOrganization(BasePermission):
    def has_permission(self, request, view):
        return bool(user_org_ids(request.user))


class IsOrgMember(BasePermission):
    """Object must expose `organization` or `organization_id`; user must belong to it."""

    def has_object_permission(self, request, view, obj):
        if is_platform_admin(request.user):
            return True
        org = getattr(obj, "organization", None)
        if org is None:
            org_id = getattr(obj, "organization_id", None)
            return org_id in user_org_ids(request.user)
        return org.id in user_org_ids(request.user)


class ReadOnly(BasePermission):
    def has_permission(self, request, view):
        return request.method in SAFE_METHODS
