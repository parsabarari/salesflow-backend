from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.audit.models import AuditActionType
from apps.core.context import clear_current_organization, set_current_organization
from apps.organizations.models import Membership, MembershipRole, Organization


class AuditLogEndpointTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.organization = Organization.objects.create(name="Acme")

        set_current_organization(self.organization.id)
        self.owner = Membership.objects.create(
            user=User.objects.create_user(email="owner@example.com", password="secret"),
            organization=self.organization,
            role=MembershipRole.OWNER,
        )
        self.admin = Membership.objects.create(
            user=User.objects.create_user(email="admin@example.com", password="secret"),
            organization=self.organization,
            role=MembershipRole.ADMIN,
        )
        self.agent = Membership.objects.create(
            user=User.objects.create_user(email="agent@example.com", password="secret"),
            organization=self.organization,
            role=MembershipRole.SALES_AGENT,
        )
        clear_current_organization()

    def _url(self):
        return f"/api/v1/organizations/{self.organization.id}/audit-logs/"

    def _generate_a_role_change_log(self):
        # Reuses the real MembershipService flow (already writes an
        # AuditLog row per Business Rules 3.3) rather than constructing
        # an AuditLog row by hand — exercises the actual write path.
        self.client.force_authenticate(user=self.owner.user)
        url = f"/api/v1/organizations/{self.organization.id}/memberships/{self.agent.id}/"
        self.client.patch(url, {"role": MembershipRole.SALES_MANAGER}, format="json")

    def test_owner_can_list_audit_logs(self):
        self._generate_a_role_change_log()
        self.client.force_authenticate(user=self.owner.user)
        response = self.client.get(self._url())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["action_type"], AuditActionType.ROLE_CHANGED)

    def test_admin_can_list_audit_logs(self):
        self._generate_a_role_change_log()
        self.client.force_authenticate(user=self.admin.user)
        response = self.client.get(self._url())
        self.assertEqual(response.status_code, 200)

    def test_sales_agent_cannot_list_audit_logs(self):
        self._generate_a_role_change_log()
        self.client.force_authenticate(user=self.agent.user)
        response = self.client.get(self._url())
        self.assertEqual(response.status_code, 403)

    def test_filter_by_action_type(self):
        self._generate_a_role_change_log()
        self.client.force_authenticate(user=self.owner.user)

        matching = self.client.get(self._url() + f"?action_type={AuditActionType.ROLE_CHANGED}")
        self.assertEqual(len(matching.data), 1)

        non_matching = self.client.get(self._url() + f"?action_type={AuditActionType.MEMBER_REMOVED}")
        self.assertEqual(len(non_matching.data), 0)

    def test_filter_by_actor(self):
        self._generate_a_role_change_log()
        self.client.force_authenticate(user=self.owner.user)

        response = self.client.get(self._url() + f"?actor={self.owner.id}")
        self.assertEqual(len(response.data), 1)

        response = self.client.get(self._url() + f"?actor={self.agent.id}")
        self.assertEqual(len(response.data), 0)

    def test_newest_first_ordering(self):
        self.client.force_authenticate(user=self.owner.user)
        url = f"/api/v1/organizations/{self.organization.id}/memberships/{self.agent.id}/"
        self.client.patch(url, {"role": MembershipRole.SALES_MANAGER}, format="json")
        self.client.patch(url, {"role": MembershipRole.SUPPORT_AGENT}, format="json")

        response = self.client.get(self._url())
        self.assertEqual(len(response.data), 2)
        self.assertGreaterEqual(response.data[0]["created_at"], response.data[1]["created_at"])
