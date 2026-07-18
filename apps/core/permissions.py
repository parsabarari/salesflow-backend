from rest_framework.permissions import BasePermission

from apps.organizations.models import Membership, MembershipRole


def get_active_membership(request):
    """Returns the requesting user's active (non-soft-deleted) Membership
    in the currently-set organization context, or None.

    Callers must ensure set_current_organization() has already run
    (OrgScopedViewSetMixin.initial() does this) since Membership.objects
    is org-scoped.

    NOTE: explicitly filters deleted_at__isnull=True — OrgScopedManager
    does not exclude soft-deleted rows on its own, so a plain
    Membership.objects.get(user=request.user) would let a removed
    member's stale role still pass a permission check.
    """
    return (
        Membership.objects.filter(user=request.user, deleted_at__isnull=True)
        .first()
    )


class IsOwnerOrAdmin(BasePermission):
    """Org Settings / Member Management column of the Permission Matrix
    (PRD 5.3) — Owner and Admin only. Used for role-change, member
    removal, and organization settings endpoints."""

    message = "Only Owner or Admin can perform this action."

    def has_permission(self, request, view):
        membership = get_active_membership(request)
        if membership is None:
            return False
        request.membership = membership  # avoid refetching in the view
        return membership.role in (MembershipRole.OWNER, MembershipRole.ADMIN)


class IsOwner(BasePermission):
    """Reserved for actions Admin explicitly cannot perform — e.g.
    ownership transfer is excluded from Admin's permissions per the
    PRD 5.3 matrix note ("Full (except ownership transfer)")."""

    message = "Only the Owner can perform this action."

    def has_permission(self, request, view):
        membership = get_active_membership(request)
        if membership is None:
            return False
        request.membership = membership
        return membership.role == MembershipRole.OWNER
    