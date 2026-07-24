from django.test import TestCase

from apps.accounts.models import User
from apps.core.context import clear_current_organization, set_current_organization
from apps.customers.models import Customer, CustomerType
from apps.organizations.models import Membership, MembershipRole, Organization
from apps.tickets.models import TicketStatus
from apps.tickets.services import TicketService


class TicketStatusTransitionTests(TestCase):
    """Business Rules 7.3: Open -> In Progress -> Resolved -> Closed,
    with Reopened allowed from Resolved or Closed back to active work."""

    def setUp(self):
        self.organization = Organization.objects.create(name="Acme")
        set_current_organization(self.organization.id)
        self.owner = Membership.objects.create(
            user=User.objects.create_user(email="owner@example.com", password="secret"),
            organization=self.organization,
            role=MembershipRole.OWNER,
        )
        self.customer = Customer.objects.create(
            organization=self.organization, type=CustomerType.INDIVIDUAL, name="Jane", email="jane@example.com"
        )
        self.ticket = TicketService.create(
            organization=self.organization, customer=self.customer, contact=None,
            subject="Issue", priority="medium", assignee=None, created_by=self.owner,
        )

    def tearDown(self):
        clear_current_organization()

    def test_open_to_in_progress(self):
        ticket = TicketService.transition_status(self.ticket, TicketStatus.IN_PROGRESS)
        self.assertEqual(ticket.status, TicketStatus.IN_PROGRESS)

    def test_open_cannot_skip_to_resolved(self):
        with self.assertRaises(ValueError):
            TicketService.transition_status(self.ticket, TicketStatus.RESOLVED)

    def test_full_happy_path_to_closed(self):
        ticket = TicketService.transition_status(self.ticket, TicketStatus.IN_PROGRESS)
        ticket = TicketService.transition_status(ticket, TicketStatus.RESOLVED)
        ticket = TicketService.transition_status(ticket, TicketStatus.CLOSED)
        self.assertEqual(ticket.status, TicketStatus.CLOSED)

    def test_closed_can_reopen(self):
        ticket = TicketService.transition_status(self.ticket, TicketStatus.IN_PROGRESS)
        ticket = TicketService.transition_status(ticket, TicketStatus.RESOLVED)
        ticket = TicketService.transition_status(ticket, TicketStatus.CLOSED)
        ticket = TicketService.transition_status(ticket, TicketStatus.REOPENED)
        self.assertEqual(ticket.status, TicketStatus.REOPENED)

    def test_resolved_can_reopen(self):
        ticket = TicketService.transition_status(self.ticket, TicketStatus.IN_PROGRESS)
        ticket = TicketService.transition_status(ticket, TicketStatus.RESOLVED)
        ticket = TicketService.transition_status(ticket, TicketStatus.REOPENED)
        self.assertEqual(ticket.status, TicketStatus.REOPENED)

    def test_closed_cannot_go_directly_to_resolved(self):
        ticket = TicketService.transition_status(self.ticket, TicketStatus.IN_PROGRESS)
        ticket = TicketService.transition_status(ticket, TicketStatus.RESOLVED)
        ticket = TicketService.transition_status(ticket, TicketStatus.CLOSED)
        with self.assertRaises(ValueError):
            TicketService.transition_status(ticket, TicketStatus.RESOLVED)

    def test_invalid_status_value_rejected(self):
        with self.assertRaises(ValueError):
            TicketService.transition_status(self.ticket, "bogus")
