from rest_framework.permissions import BasePermission
from rest_framework.permissions import SAFE_METHODS

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
    

SCOPE_FULL = "full"
SCOPE_TEAM = "team"
SCOPE_OWN = "own"
SCOPE_READONLY_ORG = "readonly_org"
SCOPE_NONE = "none"

class RoleMatrixPermission(BasePermission):
    """Generic action-level enforcement of a PRD 5.3 matrix cell.
    Views set `role_scope_map`: dict[MembershipRole, one of the SCOPE_*
    constants]. Roles absent from the map default to SCOPE_NONE — fail
    closed, not open.

    Visibility (which specific rows an "own"/"team" role can act on) is
    NOT handled here — that's RoleScopedQuerysetMixin's job (core/viewsets.py).
    Splitting it this way means an out-of-scope object 404s naturally via
    get_object() failing to find it in an already-filtered queryset,
    matching API Spec §1.5, rather than needing a permission-denied-to-404
    conversion.
    """

    def has_permission(self, request, view):
        membership = get_active_membership(request)
        if membership is None:
            return False
        request.membership = membership
        scope = getattr(view, "role_scope_map", {}).get(membership.role, SCOPE_NONE)
        request.rbac_scope = scope
        if scope == SCOPE_NONE:
            return False
        if scope == SCOPE_READONLY_ORG and request.method not in SAFE_METHODS:
            return False
        return True
