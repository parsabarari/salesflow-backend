from django.http import Http404
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_spectacular.utils import extend_schema, extend_schema_view

from apps.core.permissions import (
    RoleMatrixPermission, SCOPE_FULL, SCOPE_NONE, SCOPE_READONLY_ORG, SCOPE_TEAM,
)
from apps.core.views import OrgScopedViewSetMixin
from apps.core.viewsets import RoleScopedQuerysetMixin
from apps.customers.models import Contact
from apps.organizations.models import Membership, MembershipRole
from apps.organizations.services import TeamService
from apps.tickets.models import Ticket
from apps.tickets.serializers import TicketCreateSerializer, TicketSerializer, TicketUpdateSerializer
from apps.tickets.services import TicketService, resolve_contact, resolve_customer
from apps.notifications.models import NotificationType
from apps.notifications.services import NotificationService

# PRD 5.3 matrix, Tickets column. Sales Manager's cell reads plain "Read"
# (no "(team)" qualifier, unlike its Leads/Customers/Activities/Comments
# cells in the same row) — read literally as org-wide read-only here,
# not team-scoped read. Flagging as a judgment call, not yet in docs.
#
# Support Agent "Full (assigned/team)" -> SCOPE_TEAM with owner_field=
# "assignee". Same caveat already flagged in apps/activities/views.py:
# there's no dedicated "Support Manager" role, so "team" here reuses the
# generic Membership.reports_to relationship regardless of role — a
# Support Agent's "team" is whoever's reports_to points at them, same
# mechanism as a Sales Manager's team.
#
# Viewer: org-wide read-only, consistent with the Viewer decision
# already applied to Leads/Activities.
TICKET_ROLE_SCOPE_MAP = {
    MembershipRole.OWNER: SCOPE_FULL,
    MembershipRole.ADMIN: SCOPE_FULL,
    MembershipRole.SALES_MANAGER: SCOPE_READONLY_ORG,
    MembershipRole.SALES_AGENT: SCOPE_NONE,
    MembershipRole.SUPPORT_AGENT: SCOPE_TEAM,
    MembershipRole.VIEWER: SCOPE_READONLY_ORG,
}


def _resolve_assignee(assignee_id):
    if assignee_id is None:
        return None
    try:
        return Membership.objects.get(id=assignee_id)
    except Membership.DoesNotExist:
        raise ValueError("Invalid assignee_id.")


def _assert_can_assign(*, actor_membership, assignee, scope: str) -> None:
    """Same shape as the SCOPE_OWN guard already applied to Activities
    (apps/activities/views.py) — SCOPE_TEAM roles (Support Agent) may
    only assign Tickets to themselves or a direct report. Full/readonly
    scopes aren't restricted here; SCOPE_NONE never reaches this (blocked
    by RoleMatrixPermission before the view body runs)."""
    if assignee is None or scope != SCOPE_TEAM:
        return
    if assignee.id == actor_membership.id:
        return
    if TeamService.is_in_team(actor_membership, assignee.id):
        return
    raise ValueError("You can only assign tickets to yourself or your team.")


class TicketObjectLookupMixin(RoleScopedQuerysetMixin):
    owner_field = "assignee"

    def get_base_queryset(self):
        return Ticket.objects.all()

    def _get_object(self, ticket_id):
        try:
            return self.get_queryset().get(id=ticket_id)
        except Ticket.DoesNotExist:
            raise Http404()


@extend_schema_view(
    get=extend_schema(tags=["Tickets"]),
    post=extend_schema(tags=["Tickets"], request=TicketCreateSerializer),
)
class TicketListCreateView(OrgScopedViewSetMixin, TicketObjectLookupMixin, APIView):
    permission_classes = [IsAuthenticated, RoleMatrixPermission]
    role_scope_map = TICKET_ROLE_SCOPE_MAP

    def get_base_queryset(self):
        queryset = Ticket.objects.all()
        params = self.request.query_params
        if params.get("status"):
            queryset = queryset.filter(status=params["status"])
        if params.get("priority"):
            queryset = queryset.filter(priority=params["priority"])
        if params.get("assignee"):
            queryset = queryset.filter(assignee_id=params["assignee"])
        if params.get("customer"):
            queryset = queryset.filter(customer_id=params["customer"])
        return queryset

    def get(self, request, organization_id):
        return Response(TicketSerializer(self.get_queryset(), many=True).data)

    def post(self, request, organization_id):
        if request.rbac_scope == SCOPE_READONLY_ORG:
            return Response(status=status.HTTP_403_FORBIDDEN)

        serializer = TicketCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            customer = resolve_customer(data["customer_id"], request.membership.organization_id)
            contact = resolve_contact(data["contact_id"], request.membership.organization_id) if data.get("contact_id") else None
            assignee = _resolve_assignee(data.get("assignee_id"))
            _assert_can_assign(actor_membership=request.membership, assignee=assignee, scope=request.rbac_scope)
        except ValueError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        try:
            ticket = TicketService.create(
                organization=request.membership.organization,
                customer=customer,
                contact=contact,
                subject=data["subject"],
                priority=data.get("priority", "medium"),
                assignee=assignee,
                created_by=request.membership,
            )
        except ValueError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        if ticket.assignee_id:
            NotificationService.create(
                recipient_membership=ticket.assignee, notification_type=NotificationType.TICKET_ASSIGNED, related_object=ticket,
            )

        return Response(TicketSerializer(ticket).data, status=status.HTTP_201_CREATED)


@extend_schema_view(
    get=extend_schema(tags=["Tickets"]),
    patch=extend_schema(tags=["Tickets"], request=TicketUpdateSerializer),
    delete=extend_schema(tags=["Tickets"]),
)
class TicketDetailView(OrgScopedViewSetMixin, TicketObjectLookupMixin, APIView):
    permission_classes = [IsAuthenticated, RoleMatrixPermission]
    role_scope_map = TICKET_ROLE_SCOPE_MAP

    def get(self, request, organization_id, ticket_id):
        return Response(TicketSerializer(self._get_object(ticket_id)).data)

    def patch(self, request, organization_id, ticket_id):
        if request.rbac_scope == SCOPE_READONLY_ORG:
            return Response(status=status.HTTP_403_FORBIDDEN)

        ticket = self._get_object(ticket_id)
        serializer = TicketUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        fields = {}
        try:
            if "assignee_id" in data:
                assignee = _resolve_assignee(data["assignee_id"])
                _assert_can_assign(actor_membership=request.membership, assignee=assignee, scope=request.rbac_scope)
                fields["assignee"] = assignee
            if "contact_id" in data:
                fields["contact"] = (
                    resolve_contact(data["contact_id"], request.membership.organization_id)
                    if data["contact_id"] is not None else None
                )
            if "subject" in data:
                fields["subject"] = data["subject"]
            if "priority" in data:
                fields["priority"] = data["priority"]
        except ValueError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        try:
            if fields:
                ticket = TicketService.update_fields(ticket, **fields)
                if "assignee" in fields and ticket.assignee_id:
                    NotificationService.create(
                        recipient_membership=ticket.assignee, notification_type=NotificationType.TICKET_ASSIGNED, related_object=ticket,
                    )
            if "status" in data:
                ticket = TicketService.transition_status(ticket, data["status"])
        except ValueError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(TicketSerializer(ticket).data)

    def delete(self, request, organization_id, ticket_id):
        if request.rbac_scope == SCOPE_READONLY_ORG:
            return Response(status=status.HTTP_403_FORBIDDEN)
        ticket = self._get_object(ticket_id)
        ticket.delete()  # soft delete
        return Response(status=status.HTTP_204_NO_CONTENT)
