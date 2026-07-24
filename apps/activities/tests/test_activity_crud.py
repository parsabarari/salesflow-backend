from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.activities.models import Activity
from apps.core.context import clear_current_organization, set_current_organization
from apps.customers.models import Customer
from apps.leads.models import Lead
from apps.organizations.models import Membership, MembershipRole, Organization


class ActivityCRUDTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.organization = Organization.objects.create(name="Acme")

        set_current_organization(self.organization.id)
        self.owner = Membership.objects.create(
            user=User.objects.create_user(email="owner@example.com", password="secret"),
            organization=self.organization,
            role=MembershipRole.OWNER,
        )
        self.agent = Membership.objects.create(
            user=User.objects.create_user(email="agent@example.com", password="secret"),
            organization=self.organization,
            role=MembershipRole.SALES_AGENT,
        )
        self.lead = Lead.objects.create(
            organization=self.organization, owner=self.agent, source="web", email="lead@example.com"
        )
        self.customer = Customer.objects.create(
            organization=self.organization, type=Customer.Type.INDIVIDUAL, name="Jane Buyer", email="jane@example.com"
        )
        clear_current_organization()

    def _list_url(self):
        return f"/api/v1/organizations/{self.organization.id}/activities/"

    def _detail_url(self, activity_id):
        return f"/api/v1/organizations/{self.organization.id}/activities/{activity_id}/"

    def test_owner_can_create_activity_on_lead(self):
        self.client.force_authenticate(user=self.owner.user)
        response = self.client.post(
            self._list_url(),
            {
                "parent_type": "lead",
                "parent_id": self.lead.id,
                "assignee_id": self.agent.id,
                "type": "call",
                "due_date": "2026-08-01T10:00:00Z",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["parent_type"], "lead")
        self.assertEqual(response.data["parent_id"], self.lead.id)
        self.assertEqual(response.data["status"], "pending")

    def test_owner_can_create_activity_on_customer(self):
        self.client.force_authenticate(user=self.owner.user)
        response = self.client.post(
            self._list_url(),
            {
                "parent_type": "customer",
                "parent_id": self.customer.id,
                "assignee_id": self.agent.id,
                "type": "meeting",
                "due_date": "2026-08-01T10:00:00Z",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["parent_type"], "customer")

    def test_invalid_parent_type_rejected(self):
        self.client.force_authenticate(user=self.owner.user)
        response = self.client.post(
            self._list_url(),
            {
                "parent_type": "ticket",
                "parent_id": 1,
                "assignee_id": self.agent.id,
                "type": "task",
                "due_date": "2026-08-01T10:00:00Z",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    def test_parent_id_in_other_organization_rejected(self):
        other_organization = Organization.objects.create(name="Other")
        set_current_organization(other_organization.id)
        other_owner = Membership.objects.create(
            user=User.objects.create_user(email="stranger@example.com", password="secret"),
            organization=other_organization,
            role=MembershipRole.OWNER,
        )
        other_lead = Lead.objects.create(
            organization=other_organization, owner=other_owner, source="web", email="stranger@example.com"
        )
        clear_current_organization()

        self.client.force_authenticate(user=self.owner.user)
        response = self.client.post(
            self._list_url(),
            {
                "parent_type": "lead",
                "parent_id": other_lead.id,
                "assignee_id": self.agent.id,
                "type": "call",
                "due_date": "2026-08-01T10:00:00Z",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    def test_get_detail_and_patch_and_delete(self):
        self.client.force_authenticate(user=self.owner.user)
        create_response = self.client.post(
            self._list_url(),
            {
                "parent_type": "lead",
                "parent_id": self.lead.id,
                "assignee_id": self.agent.id,
                "type": "task",
                "due_date": "2026-08-01T10:00:00Z",
            },
            format="json",
        )
        activity_id = create_response.data["id"]

        get_response = self.client.get(self._detail_url(activity_id))
        self.assertEqual(get_response.status_code, 200)

        patch_response = self.client.patch(
            self._detail_url(activity_id), {"due_date": "2026-08-05T10:00:00Z"}, format="json"
        )
        self.assertEqual(patch_response.status_code, 200)
        self.assertEqual(patch_response.data["due_date"], "2026-08-05T10:00:00Z")

        delete_response = self.client.delete(self._detail_url(activity_id))
        self.assertEqual(delete_response.status_code, 204)

        set_current_organization(self.organization.id)
        try:
            self.assertIsNotNone(Activity.all_objects.get(id=activity_id).deleted_at)
        finally:
            clear_current_organization()

    def test_filter_by_parent_requires_both_params(self):
        self.client.force_authenticate(user=self.owner.user)
        response = self.client.get(self._list_url() + f"?parent_type=lead")
        self.assertEqual(response.status_code, 400)

    def test_filter_by_parent(self):
        self.client.force_authenticate(user=self.owner.user)
        self.client.post(
            self._list_url(),
            {
                "parent_type": "lead",
                "parent_id": self.lead.id,
                "assignee_id": self.agent.id,
                "type": "call",
                "due_date": "2026-08-01T10:00:00Z",
            },
            format="json",
        )
        self.client.post(
            self._list_url(),
            {
                "parent_type": "customer",
                "parent_id": self.customer.id,
                "assignee_id": self.agent.id,
                "type": "meeting",
                "due_date": "2026-08-01T10:00:00Z",
            },
            format="json",
        )
        response = self.client.get(self._list_url() + f"?parent_type=lead&parent_id={self.lead.id}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["parent_type"], "lead")
