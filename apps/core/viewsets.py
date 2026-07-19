from apps.core.permissions import SCOPE_FULL, SCOPE_NONE, SCOPE_OWN, SCOPE_READONLY_ORG, SCOPE_TEAM
from apps.organizations.services import TeamService


class OrganizationScopedQuerysetMixin:
    organization_url_kwarg = "organization_id"

    def get_queryset(self):
        queryset = super().get_queryset()
        organization_id = self.kwargs[self.organization_url_kwarg]
        return queryset.for_organization(organization_id)


class RoleScopedQuerysetMixin:
    """Filters visibility per the scope RoleMatrixPermission resolved onto
    request.rbac_scope. Must run after that permission class (i.e. it
    must be in permission_classes) since this reads request.rbac_scope /
    request.membership, both set there.

    Subclasses implement get_base_queryset() instead of setting a class-
    level `queryset` attribute — the latter would evaluate an org-scoped
    manager's get_queryset() at class-definition time, before any
    request/org context exists, and crash on import.
    """

    owner_field = "owner"

    def get_base_queryset(self):
        raise NotImplementedError("Subclasses must implement get_base_queryset().")

    def get_queryset(self):
        queryset = self.get_base_queryset()
        scope = getattr(self.request, "rbac_scope", SCOPE_NONE)
        membership = self.request.membership

        if scope in (SCOPE_FULL, SCOPE_READONLY_ORG):
            return queryset
        if scope == SCOPE_OWN:
            return queryset.filter(**{self.owner_field: membership})
        if scope == SCOPE_TEAM:
            # Sales Manager's own Leads + direct reports' Leads (clarified
            # decision — matrix's "Full (team)" includes the manager's
            # own book, not only their reports').
            team_ids = TeamService.team_membership_ids(membership) + [membership.id]
            return queryset.filter(**{f"{self.owner_field}_id__in": team_ids})
        return queryset.none()
