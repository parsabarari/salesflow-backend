from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.core.context import clear_current_organization, set_current_organization
from apps.customers.models import Contact, Customer, CustomerType
from apps.organizations.models import Membership, MembershipRole, Organization
from apps.tickets.models import Ticket


class TicketCRUDTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.organization = Organization.objects.create(name="Acme")

        set_current_organization(self.organization.id)
        self.owner = Membership.objects.create(
            user=User.objects.create_user(email="owner@example.com", password="secret"),
            organization=self.organization,
            role=MembershipRole.OWNER,
        )
        self.support = Membership.objects.create(
            user=User.objects.create_user(email="support@example.com", password="secret"),
            organization=self.organization,
            role=MembershipRole.SUPPORT_AGENT,
        )
        self.customer = Customer.objects.create(
            organization=self.organization, type=CustomerType.COMPANY, name="Acme Corp"
        )
        self.contact = Contact.objects.create(customer=self.customer, name="Bob", email="bob@acmecorp.com")

        self.other_customer = Customer.objects.create(
            organization=self.organization, type=CustomerType.INDIVIDUAL, name="Jane", email="jane@example.com"
        )
        clear_current_organization()

    def _list_url(self):
        return f"/api/v1/organizations/{self.organization.id}/tickets/"

    def _detail_url(self, ticket_id):
        return f"/api/v1/organizations/{self.organization.id}/tickets/{ticket_id}/"

    def test_owner_can_create_ticket(self):
        self.client.force_authenticate(user=self.owner.user)
        response = self.client.post(
            self._list_url(),
            {"customer_id": self.customer.id, "subject": "Broken widget", "assignee_id": self.support.id},
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["status"], "open")
        self.assertEqual(response.data["priority"], "medium")

    def test_create_with_contact_belonging_to_customer(self):
        self.client.force_authenticate(user=self.owner.user)
        response = self.client.post(
            self._list_url(),
            {"customer_id": self.customer.id, "contact_id": self.contact.id, "subject": "Issue"},
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["contact_id"], self.contact.id)

    def test_create_with_contact_not_belonging_to_customer_rejected(self):
        self.client.force_authenticate(user=self.owner.user)
        response = self.client.post(
            self._list_url(),
            {"customer_id": self.other_customer.id, "contact_id": self.contact.id, "subject": "Issue"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    def test_create_with_customer_in_other_org_rejected(self):
        other_organization = Organization.objects.create(name="Other")
        set_current_organization(other_organization.id)
        other_customer = Customer.objects.create(
            organization=other_organization, type=CustomerType.INDIVIDUAL, name="Stranger", email="s@example.com"
        )
        clear_current_organization()

        self.client.force_authenticate(user=self.owner.user)
        response = self.client.post(
            self._list_url(),
            {"customer_id": other_customer.id, "subject": "Issue"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    def test_get_detail_patch_and_delete(self):
        self.client.force_authenticate(user=self.owner.user)
        create_response = self.client.post(
            self._list_url(), {"customer_id": self.customer.id, "subject": "Issue"}, format="json"
        )
        ticket_id = create_response.data["id"]

        get_response = self.client.get(self._detail_url(ticket_id))
        self.assertEqual(get_response.status_code, 200)

        patch_response = self.client.patch(self._detail_url(ticket_id), {"subject": "Updated issue"}, format="json")
        self.assertEqual(patch_response.status_code, 200)
        self.assertEqual(patch_response.data["subject"], "Updated issue")

        delete_response = self.client.delete(self._detail_url(ticket_id))
        self.assertEqual(delete_response.status_code, 204)

        set_current_organization(self.organization.id)
        try:
            self.assertIsNotNone(Ticket.all_objects.get(id=ticket_id).deleted_at)
        finally:
            clear_current_organization()

    def test_filter_by_status_and_customer(self):
        self.client.force_authenticate(user=self.owner.user)
        self.client.post(self._list_url(), {"customer_id": self.customer.id, "subject": "A"}, format="json")
        self.client.post(self._list_url(), {"customer_id": self.other_customer.id, "subject": "B"}, format="json")

        response = self.client.get(self._list_url() + f"?customer={self.customer.id}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["subject"], "A")
