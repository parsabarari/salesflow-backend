from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.core.context import clear_current_organization, set_current_organization
from apps.customers.models import Contact, Customer, CustomerType
from apps.organizations.models import Membership, MembershipRole, Organization


class CustomerContactRestoreTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.organization = Organization.objects.create(name="Acme")
        set_current_organization(self.organization.id)
        self.owner = Membership.objects.create(
            user=User.objects.create_user(email="owner@example.com", password="secret"),
            organization=self.organization, role=MembershipRole.OWNER,
        )
        self.agent = Membership.objects.create(
            user=User.objects.create_user(email="agent@example.com", password="secret"),
            organization=self.organization, role=MembershipRole.SALES_AGENT,
        )
        self.customer = Customer.objects.create(
            organization=self.organization, type=CustomerType.INDIVIDUAL, name="Jane", email="jane@example.com",
        )
        self.contact = Contact.objects.create(customer=self.customer, name="Bob", email="bob@example.com")
        self.customer.delete()
        self.contact.delete()
        clear_current_organization()

    def test_owner_can_restore_customer(self):
        self.client.force_authenticate(user=self.owner.user)
        response = self.client.post(
            f"/api/v1/organizations/{self.organization.id}/customers/{self.customer.id}/restore/"
        )
        self.assertEqual(response.status_code, 200)

        set_current_organization(self.organization.id)
        try:
            self.customer.refresh_from_db()
        finally:
            clear_current_organization()
        self.assertIsNone(self.customer.deleted_at)

    def test_sales_agent_cannot_restore_customer(self):
        self.client.force_authenticate(user=self.agent.user)
        response = self.client.post(
            f"/api/v1/organizations/{self.organization.id}/customers/{self.customer.id}/restore/"
        )
        self.assertEqual(response.status_code, 403)

    def test_owner_can_restore_contact(self):
        self.client.force_authenticate(user=self.owner.user)
        response = self.client.post(
            f"/api/v1/organizations/{self.organization.id}/contacts/{self.contact.id}/restore/"
        )
        self.assertEqual(response.status_code, 200)

        set_current_organization(self.organization.id)
        try:
            self.contact.refresh_from_db()
        finally:
            clear_current_organization()
        self.assertIsNone(self.contact.deleted_at)

    def test_restoring_active_customer_returns_404(self):
        set_current_organization(self.organization.id)
        try:
            self.customer.restore()
        finally:
            clear_current_organization()

        self.client.force_authenticate(user=self.owner.user)
        response = self.client.post(
            f"/api/v1/organizations/{self.organization.id}/customers/{self.customer.id}/restore/"
        )
        self.assertEqual(response.status_code, 404)
