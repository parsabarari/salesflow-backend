from apps.core.permissions import SCOPE_NONE, SCOPE_OWN, SCOPE_TEAM
from apps.organizations.services import TeamService


def resolve_parent_scope(*, membership, role, parent) -> str:
    from apps.customers.models import Customer
    from apps.leads.models import Lead
    from apps.tickets.models import Ticket

    if isinstance(parent, Lead):
        from apps.leads.views import LEAD_ROLE_SCOPE_MAP
        scope = LEAD_ROLE_SCOPE_MAP.get(role, SCOPE_NONE)
        if scope == SCOPE_OWN:
            return scope if parent.owner_id == membership.id else SCOPE_NONE
        if scope == SCOPE_TEAM:
            team_ids = TeamService.team_membership_ids(membership) + [membership.id]
            return scope if parent.owner_id in team_ids else SCOPE_NONE
        return scope

    if isinstance(parent, Customer):
        from apps.customers.views import CUSTOMER_ROLE_SCOPE_MAP
        scope = CUSTOMER_ROLE_SCOPE_MAP.get(role, SCOPE_NONE)
        if scope == SCOPE_OWN:
            visible = parent.lead_links.filter(lead__owner=membership).exists()
            return scope if visible else SCOPE_NONE
        if scope == SCOPE_TEAM:
            team_ids = TeamService.team_membership_ids(membership) + [membership.id]
            visible = parent.lead_links.filter(lead__owner_id__in=team_ids).exists()
            return scope if visible else SCOPE_NONE
        return scope

    if isinstance(parent, Ticket):
        from apps.tickets.views import TICKET_ROLE_SCOPE_MAP
        scope = TICKET_ROLE_SCOPE_MAP.get(role, SCOPE_NONE)
        if scope == SCOPE_TEAM:
            team_ids = TeamService.team_membership_ids(membership) + [membership.id]
            return scope if parent.assignee_id in team_ids else SCOPE_NONE
        return scope

    return SCOPE_NONE
