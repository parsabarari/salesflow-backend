from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.core.context import clear_current_organization, set_current_organization
from apps.customers.models import Customer, CustomerType
from apps.leads.services import LeadService
from apps.organizations.models import Membership, MembershipRole, Organization
from apps.tickets.services import TicketService


class GlobalSearchTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.organization = Organization.objects.create(name="Acme")

        set_current_organization(self.organization.id)
        self.owner = Membership.objects.create(
            user=User.objects.create_user(email="owner@example.com", password="secret"),
            organization=self.organization,
            role=MembershipRole.OWNER,
        )
        self.agent_a = Membership.objects.create(
            user=User.objects.create_user(email="agenta@example.com", password="secret"),
            organization=self.organization,
            role=MembershipRole.SALES_AGENT,
        )
        self.agent_b = Membership.objects.create(
            user=User.objects.create_user(email="agentb@example.com", password="secret"),
            organization=self.organization,
            role=MembershipRole.SALES_AGENT,
        )

        self.lead_a = LeadService.create_lead(
            organization=self.organization, owner=self.agent_a, source="referral", email="findme-a@example.com"
        )
        self.lead_b = LeadService.create_lead(
            organization=self.organization, owner=self.agent_b, source="referral", email="findme-b@example.com"
        )

        self.customer = Customer.objects.create(
            organization=self.organization, type=CustomerType.INDIVIDUAL, name="Findme Customer", email="c@example.com"
        )
        from apps.customers.models import CustomerLeadLink
        CustomerLeadLink.objects.create(customer=self.customer, lead=self.lead_a)

        self.ticket = TicketService.create(
            organization=self.organization, customer=self.customer, contact=None,
            subject="Findme ticket issue", priority="medium", assignee=self.agent_a, created_by=self.owner,
        )
        clear_current_organization()

    def _url(self, query):
        return f"/api/v1/organizations/{self.organization.id}/search/?q={query}"

    def test_missing_query_param_rejected(self):
        self.client.force_authenticate(user=self.owner.user)
        response = self.client.get(f"/api/v1/organizations/{self.organization.id}/search/")
        self.assertEqual(response.status_code, 400)

    def test_owner_sees_all_matching_leads(self):
        self.client.force_authenticate(user=self.owner.user)
        response = self.client.get(self._url("findme"))
        lead_ids = {lead["id"] for lead in response.data["leads"]}
        self.assertEqual(lead_ids, {self.lead_a.id, self.lead_b.id})

    def test_sales_agent_search_does_not_surface_another_agents_lead(self):
        self.client.force_authenticate(user=self.agent_a.user)
        response = self.client.get(self._url("findme"))
        lead_ids = {lead["id"] for lead in response.data["leads"]}
        self.assertEqual(lead_ids, {self.lead_a.id})
        self.assertNotIn(self.lead_b.id, lead_ids)

    def test_sales_agent_sees_customer_via_own_lead_link(self):
        self.client.force_authenticate(user=self.agent_a.user)
        response = self.client.get(self._url("findme"))
        customer_ids = {c["id"] for c in response.data["customers"]}
        self.assertEqual(customer_ids, {self.customer.id})

    def test_sales_agent_without_lead_link_sees_no_customers(self):
        self.client.force_authenticate(user=self.agent_b.user)
        response = self.client.get(self._url("findme"))
        self.assertEqual(response.data["customers"], [])

    def test_sales_agent_has_no_ticket_visibility(self):
        # Sales Agent's Tickets cell is "—" (SCOPE_NONE) per PRD 5.3.
        self.client.force_authenticate(user=self.agent_a.user)
        response = self.client.get(self._url("findme"))
        self.assertEqual(response.data["tickets"], [])

    def test_support_agent_sees_assigned_ticket(self):
        support = Membership.objects.create(
            user=User.objects.create_user(email="support@example.com", password="secret"),
            organization=self.organization,
            role=MembershipRole.SUPPORT_AGENT,
        )
        set_current_organization(self.organization.id)
        try:
            self.ticket.assignee = support
            self.ticket.save(update_fields=["assignee"])
        finally:
            clear_current_organization()

        self.client.force_authenticate(user=support.user)
        response = self.client.get(self._url("findme"))
        ticket_ids = {t["id"] for t in response.data["tickets"]}
        self.assertEqual(ticket_ids, {self.ticket.id})

    def test_no_match_returns_empty_lists(self):
        self.client.force_authenticate(user=self.owner.user)
        response = self.client.get(self._url("nonexistentquery12345"))
        self.assertEqual(response.data, {"leads": [], "customers": [], "tickets": []})
