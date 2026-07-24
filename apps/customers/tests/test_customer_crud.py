from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.core.context import clear_current_organization, set_current_organization
from apps.customers.models import Contact, Customer, CustomerType
from apps.leads.services import LeadService
from apps.organizations.models import Membership, MembershipRole, Organization


class CustomerContactCRUDTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.organization = Organization.objects.create(name="Acme")
        set_current_organization(self.organization.id)
        self.owner = Membership.objects.create(user=User.objects.create_user(email="owner@example.com", password="secret"), organization=self.organization, role=MembershipRole.OWNER)
        self.agent_a = Membership.objects.create(user=User.objects.create_user(email="agenta@example.com", password="secret"), organization=self.organization, role=MembershipRole.SALES_AGENT)
        self.agent_b = Membership.objects.create(user=User.objects.create_user(email="agentb@example.com", password="secret"), organization=self.organization, role=MembershipRole.SALES_AGENT)

        self.customer = Customer.objects.create(organization=self.organization, type=CustomerType.COMPANY, name="Acme Corp")
        self.contact = Contact.objects.create(customer=self.customer, name="Bob", email="bob@acmecorp.com")

        lead_a = LeadService.create_lead(organization=self.organization, owner=self.agent_a, source="web", email="won@example.com")
        from apps.customers.models import CustomerLeadLink
        CustomerLeadLink.objects.create(customer=self.customer, lead=lead_a)
        clear_current_organization()

    def test_agent_sees_customer_linked_to_own_lead(self):
        self.client.force_authenticate(user=self.agent_a.user)
        response = self.client.get(f"/api/v1/organizations/{self.organization.id}/customers/")
        ids = {c["id"] for c in response.data}
        self.assertEqual(ids, {self.customer.id})

    def test_agent_without_linked_lead_sees_nothing(self):
        self.client.force_authenticate(user=self.agent_b.user)
        response = self.client.get(f"/api/v1/organizations/{self.organization.id}/customers/")
        self.assertEqual(response.data, [])

    def test_owner_sees_all_customers(self):
        self.client.force_authenticate(user=self.owner.user)
        response = self.client.get(f"/api/v1/organizations/{self.organization.id}/customers/")
        ids = {c["id"] for c in response.data}
        self.assertEqual(ids, {self.customer.id})

    def test_cannot_remove_last_contact_of_company(self):
        self.client.force_authenticate(user=self.owner.user)
        url = f"/api/v1/organizations/{self.organization.id}/contacts/{self.contact.id}/"
        response = self.client.delete(url)
        self.assertEqual(response.status_code, 400)

    def test_can_remove_contact_when_another_remains(self):
        set_current_organization(self.organization.id)
        try:
            Contact.objects.create(customer=self.customer, name="Carol", email="carol@acmecorp.com")
        finally:
            clear_current_organization()

        self.client.force_authenticate(user=self.owner.user)
        url = f"/api/v1/organizations/{self.organization.id}/contacts/{self.contact.id}/"
        response = self.client.delete(url)
        self.assertEqual(response.status_code, 204)

    def test_patch_customer(self):
        self.client.force_authenticate(user=self.owner.user)
        url = f"/api/v1/organizations/{self.organization.id}/customers/{self.customer.id}/"
        response = self.client.patch(url, {"name": "Acme Corp Renamed"}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["name"], "Acme Corp Renamed")
