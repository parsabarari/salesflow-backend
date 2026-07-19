from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.core.context import clear_current_organization, set_current_organization
from apps.leads.models import Lead
from apps.organizations.models import Membership, MembershipRole, Organization


class LeadRBACTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.organization = Organization.objects.create(name="Acme")

        set_current_organization(self.organization.id)
        self.owner = Membership.objects.create(user=User.objects.create_user(email="owner@example.com", password="secret"), organization=self.organization, role=MembershipRole.OWNER)
        self.manager = Membership.objects.create(user=User.objects.create_user(email="manager@example.com", password="secret"), organization=self.organization, role=MembershipRole.SALES_MANAGER)
        self.agent_a = Membership.objects.create(user=User.objects.create_user(email="agenta@example.com", password="secret"), organization=self.organization, role=MembershipRole.SALES_AGENT, reports_to=self.manager)
        self.agent_b = Membership.objects.create(user=User.objects.create_user(email="agentb@example.com", password="secret"), organization=self.organization, role=MembershipRole.SALES_AGENT)
        self.support = Membership.objects.create(user=User.objects.create_user(email="support@example.com", password="secret"), organization=self.organization, role=MembershipRole.SUPPORT_AGENT)
        self.viewer = Membership.objects.create(user=User.objects.create_user(email="viewer@example.com", password="secret"), organization=self.organization, role=MembershipRole.VIEWER)

        self.lead_a = Lead.objects.create(organization=self.organization, owner=self.agent_a, source="web", email="a@example.com")
        self.lead_b = Lead.objects.create(organization=self.organization, owner=self.agent_b, source="web", email="b@example.com")
        clear_current_organization()

    def _list_url(self):
        return f"/api/v1/organizations/{self.organization.id}/leads/"

    def test_sales_agent_sees_only_own_leads(self):
        self.client.force_authenticate(user=self.agent_a.user)
        response = self.client.get(self._list_url())
        ids = {lead["id"] for lead in response.data}
        self.assertEqual(ids, {self.lead_a.id})

    def test_sales_manager_sees_own_plus_team_leads(self):
        self.client.force_authenticate(user=self.manager.user)
        response = self.client.get(self._list_url())
        ids = {lead["id"] for lead in response.data}
        self.assertEqual(ids, {self.lead_a.id})  # agent_a reports to manager; agent_b does not
        self.assertNotIn(self.lead_b.id, ids)

    def test_owner_sees_all_leads(self):
        self.client.force_authenticate(user=self.owner.user)
        response = self.client.get(self._list_url())
        ids = {lead["id"] for lead in response.data}
        self.assertEqual(ids, {self.lead_a.id, self.lead_b.id})

    def test_support_agent_has_no_lead_access(self):
        self.client.force_authenticate(user=self.support.user)
        response = self.client.get(self._list_url())
        self.assertEqual(response.status_code, 403)

    def test_viewer_sees_all_leads_but_cannot_write(self):
        self.client.force_authenticate(user=self.viewer.user)
        response = self.client.get(self._list_url())
        ids = {lead["id"] for lead in response.data}
        self.assertEqual(ids, {self.lead_a.id, self.lead_b.id})

        response = self.client.post(self._list_url(), {"owner_id": self.viewer.id, "source": "web", "email": "x@example.com"}, format="json")
        self.assertEqual(response.status_code, 403)

    def test_sales_agent_cannot_assign_lead_to_someone_else(self):
        self.client.force_authenticate(user=self.agent_a.user)
        response = self.client.post(self._list_url(), {"owner_id": self.agent_b.id, "source": "web", "email": "x@example.com"}, format="json")
        self.assertEqual(response.status_code, 400)
