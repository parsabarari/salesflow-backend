from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.core.context import clear_current_organization, set_current_organization
from apps.leads.models import Lead
from apps.organizations.models import Membership, MembershipRole, Organization


class ActivityRBACTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.organization = Organization.objects.create(name="Acme")

        set_current_organization(self.organization.id)
        self.manager = Membership.objects.create(
            user=User.objects.create_user(email="manager@example.com", password="secret"),
            organization=self.organization,
            role=MembershipRole.SALES_MANAGER,
        )
        self.agent_a = Membership.objects.create(
            user=User.objects.create_user(email="agenta@example.com", password="secret"),
            organization=self.organization,
            role=MembershipRole.SALES_AGENT,
            reports_to=self.manager,
        )
        self.agent_b = Membership.objects.create(
            user=User.objects.create_user(email="agentb@example.com", password="secret"),
            organization=self.organization,
            role=MembershipRole.SALES_AGENT,
        )
        self.support = Membership.objects.create(
            user=User.objects.create_user(email="support@example.com", password="secret"),
            organization=self.organization,
            role=MembershipRole.SUPPORT_AGENT,
        )
        self.viewer = Membership.objects.create(
            user=User.objects.create_user(email="viewer@example.com", password="secret"),
            organization=self.organization,
            role=MembershipRole.VIEWER,
        )

        self.lead = Lead.objects.create(
            organization=self.organization, owner=self.agent_a, source="web", email="lead@example.com"
        )
        clear_current_organization()

    def _list_url(self):
        return f"/api/v1/organizations/{self.organization.id}/activities/"

    def _create_as(self, membership, assignee):
        self.client.force_authenticate(user=membership.user)
        return self.client.post(
            self._list_url(),
            {
                "parent_type": "lead",
                "parent_id": self.lead.id,
                "assignee_id": assignee.id,
                "type": "call",
                "due_date": "2026-08-01T10:00:00Z",
            },
            format="json",
        )

    def test_sales_agent_can_create_activity_for_self(self):
        response = self._create_as(self.agent_a, self.agent_a)
        self.assertEqual(response.status_code, 201)

    def test_sales_agent_cannot_create_activity_for_someone_else(self):
        response = self._create_as(self.agent_a, self.agent_b)
        self.assertEqual(response.status_code, 400)

    def test_support_agent_can_create_activity_for_self(self):
        response = self._create_as(self.support, self.support)
        self.assertEqual(response.status_code, 201)

    def test_support_agent_cannot_create_activity_for_someone_else(self):
        response = self._create_as(self.support, self.agent_a)
        self.assertEqual(response.status_code, 400)

    def test_sales_agent_sees_only_own_activities(self):
        self._create_as(self.agent_a, self.agent_a)
        self._create_as(self.support, self.support)

        self.client.force_authenticate(user=self.agent_a.user)
        response = self.client.get(self._list_url())
        self.assertEqual(response.status_code, 200)
        assignee_ids = {a["assignee_id"] for a in response.data}
        self.assertEqual(assignee_ids, {self.agent_a.id})

    def test_sales_manager_sees_own_plus_team_activities(self):
        self._create_as(self.agent_a, self.agent_a)  # agent_a reports to manager
        self._create_as(self.agent_b, self.agent_b)  # agent_b does not

        self.client.force_authenticate(user=self.manager.user)
        response = self.client.get(self._list_url())
        assignee_ids = {a["assignee_id"] for a in response.data}
        self.assertIn(self.agent_a.id, assignee_ids)
        self.assertNotIn(self.agent_b.id, assignee_ids)

    def test_viewer_sees_all_but_cannot_write(self):
        self._create_as(self.agent_a, self.agent_a)

        self.client.force_authenticate(user=self.viewer.user)
        get_response = self.client.get(self._list_url())
        self.assertEqual(get_response.status_code, 200)
        self.assertEqual(len(get_response.data), 1)

        post_response = self.client.post(
            self._list_url(),
            {
                "parent_type": "lead",
                "parent_id": self.lead.id,
                "assignee_id": self.viewer.id,
                "type": "call",
                "due_date": "2026-08-01T10:00:00Z",
            },
            format="json",
        )
        self.assertEqual(post_response.status_code, 403)
