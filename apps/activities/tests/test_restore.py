from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.activities.services import ActivityService
from apps.core.context import clear_current_organization, set_current_organization
from apps.leads.models import Lead
from apps.organizations.models import Membership, MembershipRole, Organization


class ActivityRestoreTests(TestCase):
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
        self.lead = Lead.objects.create(
            organization=self.organization, owner=self.agent, source="web", email="lead@example.com",
        )
        self.activity = ActivityService.create(
            organization=self.organization, parent_type="lead", parent_id=self.lead.id,
            assignee=self.agent, activity_type="task", due_date="2026-08-01T10:00:00Z",
        )
        self.activity.delete()
        clear_current_organization()

    def _url(self, activity_id):
        return f"/api/v1/organizations/{self.organization.id}/activities/{activity_id}/restore/"

    def test_owner_can_restore(self):
        self.client.force_authenticate(user=self.owner.user)
        response = self.client.post(self._url(self.activity.id))
        self.assertEqual(response.status_code, 200)

    def test_sales_agent_cannot_restore_even_own_activity(self):
        # Restore is Owner/Admin-only per Business Rules 12.3 — not
        # gated by the Activities RBAC matrix (own/team/full), since
        # this is a recovery action, not routine CRUD.
        self.client.force_authenticate(user=self.agent.user)
        response = self.client.post(self._url(self.activity.id))
        self.assertEqual(response.status_code, 403)
