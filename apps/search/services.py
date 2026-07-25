from django.db.models import Q

from apps.core.permissions import SCOPE_FULL, SCOPE_OWN, SCOPE_READONLY_ORG, SCOPE_TEAM
from apps.customers.models import Customer
from apps.leads.models import Lead
from apps.organizations.services import TeamService
from apps.tickets.models import Ticket


def _owner_scoped_filter(queryset, *, scope: str, owner_field: str, membership):
    if scope in (SCOPE_FULL, SCOPE_READONLY_ORG):
        return queryset
    if scope == SCOPE_OWN:
        return queryset.filter(**{owner_field: membership})
    if scope == SCOPE_TEAM:
        team_ids = TeamService.team_membership_ids(membership) + [membership.id]
        return queryset.filter(**{f"{owner_field}_id__in": team_ids})
    return queryset.none()


class SearchService:
    @staticmethod
    def search(*, query: str, membership, role: str) -> dict:
        from apps.customers.views import CUSTOMER_ROLE_SCOPE_MAP
        from apps.leads.views import LEAD_ROLE_SCOPE_MAP
        from apps.tickets.views import TICKET_ROLE_SCOPE_MAP

        return {
            "leads": SearchService._search_leads(query, membership, role, LEAD_ROLE_SCOPE_MAP),
            "customers": SearchService._search_customers(query, membership, role, CUSTOMER_ROLE_SCOPE_MAP),
            "tickets": SearchService._search_tickets(query, membership, role, TICKET_ROLE_SCOPE_MAP),
        }

    @staticmethod
    def _search_leads(query, membership, role, role_scope_map) -> list:
        scope = role_scope_map.get(role, "none")
        queryset = Lead.objects.filter(is_archived=False).filter(
            Q(email__icontains=query) | Q(phone__icontains=query) | Q(source__icontains=query)
        )
        queryset = _owner_scoped_filter(queryset, scope=scope, owner_field="owner", membership=membership)
        return list(queryset.values("id", "email", "phone", "stage")[:20])

    @staticmethod
    def _search_customers(query, membership, role, role_scope_map) -> list:
        scope = role_scope_map.get(role, "none")
        queryset = Customer.objects.filter(
            Q(name__icontains=query) | Q(email__icontains=query) | Q(phone__icontains=query)
        )
        if scope in (SCOPE_FULL, SCOPE_READONLY_ORG):
            pass
        elif scope == SCOPE_OWN:
            queryset = queryset.filter(lead_links__lead__owner=membership).distinct()
        elif scope == SCOPE_TEAM:
            team_ids = TeamService.team_membership_ids(membership) + [membership.id]
            queryset = queryset.filter(lead_links__lead__owner_id__in=team_ids).distinct()
        else:
            queryset = queryset.none()
        return list(queryset.values("id", "name", "email", "phone", "type")[:20])

    @staticmethod
    def _search_tickets(query, membership, role, role_scope_map) -> list:
        scope = role_scope_map.get(role, "none")
        queryset = Ticket.objects.filter(subject__icontains=query)
        queryset = _owner_scoped_filter(queryset, scope=scope, owner_field="assignee", membership=membership)
        return list(queryset.values("id", "subject", "status", "priority")[:20])
