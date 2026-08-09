from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.core.context import clear_current_organization, set_current_organization
from apps.customers.models import Customer, CustomerType
from apps.organizations.models import Membership, MembershipRole, Organization
from apps.tickets.services import TicketService


class TicketRestoreTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.organization = Organization.objects.create(name="Acme")
        set_current_organization(self.organization.id)
        self.owner = Membership.objects.create(
            user=User.objects.create_user(email="owner@example.com", password="secret"),
            organization=self.organization, role=MembershipRole.OWNER,
        )
        self.support = Membership.objects.create(
            user=User.objects.create_user(email="support@example.com", password="secret"),
            organization=self.organization, role=MembershipRole.SUPPORT_AGENT,
        )
        self.customer = Customer.objects.create(
            organization=self.organization, type=CustomerType.INDIVIDUAL, name="Jane", email="jane@example.com",
        )
        self.ticket = TicketService.create(
            organization=self.organization, customer=self.customer, contact=None,
            subject="Issue", priority="medium", assignee=self.support, created_by=self.owner,
        )
        self.ticket.delete()
        clear_current_organization()

    def _url(self, ticket_id):
        return f"/api/v1/organizations/{self.organization.id}/tickets/{ticket_id}/restore/"

    def test_owner_can_restore(self):
        self.client.force_authenticate(user=self.owner.user)
        response = self.client.post(self._url(self.ticket.id))
        self.assertEqual(response.status_code, 200)

    def test_support_agent_cannot_restore(self):
        self.client.force_authenticate(user=self.support.user)
        response = self.client.post(self._url(self.ticket.id))
        self.assertEqual(response.status_code, 403)
