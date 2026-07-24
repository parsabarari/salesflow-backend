from django.db import transaction

from apps.customers.models import Contact, Customer
from apps.tickets.models import Ticket, TicketStatus

# Business Rules 7.3: "Open → In Progress → Resolved → Closed, with
# Reopened allowed from Resolved or Closed back to Open." Read literally
# as a sequential flow (no explicit "free movement between non-terminal
# stages" permission like Leads got in Business Rules 5.2) — so this is
# modeled as strict forward progression, with Reopened as the only way
# back into active work from Resolved/Closed. ASSUMPTION (flagging, not
# explicitly spelled out): once Reopened, a ticket can move to
# In Progress or straight back to Resolved, mirroring the original
# flow's shape rather than requiring it to pass through "Open" again
# (there's no path back to the literal 'open' status once left — only
# 'reopened' represents "active again," which matches ERD §16's 5-value
# enum where 'reopened' is its own status, not an alias for 'open').
TICKET_STATUS_TRANSITIONS = {
    TicketStatus.OPEN: {TicketStatus.IN_PROGRESS},
    TicketStatus.IN_PROGRESS: {TicketStatus.RESOLVED},
    TicketStatus.RESOLVED: {TicketStatus.CLOSED, TicketStatus.REOPENED},
    TicketStatus.CLOSED: {TicketStatus.REOPENED},
    TicketStatus.REOPENED: {TicketStatus.IN_PROGRESS, TicketStatus.RESOLVED},
}


def assert_contact_belongs_to_customer(*, customer, contact) -> None:
    """ERD §16 cross-column check: if contact_id is set, its customer_id
    must match the Ticket's own customer_id. Not expressible as a DB
    CHECK constraint, enforced here instead."""
    if contact is not None and contact.customer_id != customer.id:
        raise ValueError("contact must belong to the specified customer.")


def resolve_customer(customer_id: int, organization_id: int) -> Customer:
    """Same explicit-organization_id pattern as
    apps/activities/services.py::resolve_parent — validated against the
    passed organization_id rather than only ambient context, so a
    cross-org customer_id can never be attached to a Ticket."""
    try:
        return Customer.all_objects.get(id=customer_id, organization_id=organization_id, deleted_at__isnull=True)
    except Customer.DoesNotExist:
        raise ValueError(f"No customer with id={customer_id} in this organization.")


def resolve_contact(contact_id: int, organization_id: int):
    """Contact has no organization_id of its own (ERD §10) — reachable
    only via customer_id -> customer.organization_id. Contact.all_objects
    is already org-scoped through the ambient context (which is set by
    OrgScopedViewSetMixin for the whole request, matching organization_id
    here), same pattern as Contact's own manager in apps/customers/models.py."""
    try:
        return Contact.all_objects.get(id=contact_id, deleted_at__isnull=True)
    except Contact.DoesNotExist:
        raise ValueError(f"No contact with id={contact_id} in this organization.")


class TicketService:
    @staticmethod
    @transaction.atomic
    def create(*, organization, customer, contact, subject, priority, assignee, created_by) -> Ticket:
        assert_contact_belongs_to_customer(customer=customer, contact=contact)
        return Ticket.objects.create(
            organization=organization,
            customer=customer,
            contact=contact,
            subject=subject,
            priority=priority,
            assignee=assignee,
            created_by=created_by,
        )

    @staticmethod
    def update_fields(ticket: Ticket, **fields) -> Ticket:
        """Plain field edits (subject, priority, assignee, contact) —
        status changes go through transition_status() below, since that
        path carries the Business Rules 7.3 transition validation a
        generic field-set shouldn't silently bypass (same split already
        used for Activity in apps/activities/services.py)."""
        if "contact" in fields:
            assert_contact_belongs_to_customer(customer=ticket.customer, contact=fields["contact"])
        for field, value in fields.items():
            setattr(ticket, field, value)
        ticket.save(update_fields=list(fields.keys()))
        return ticket

    @staticmethod
    def transition_status(ticket: Ticket, to_status: str) -> Ticket:
        if to_status not in TicketStatus.values:
            raise ValueError(f"'{to_status}' is not a valid status.")
        allowed = TICKET_STATUS_TRANSITIONS.get(ticket.status, set())
        if to_status not in allowed:
            raise ValueError(f"Cannot transition from '{ticket.status}' to '{to_status}'.")
        ticket.status = to_status
        ticket.save(update_fields=["status"])
        return ticket
