from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.core.context import clear_current_organization, set_current_organization
from apps.organizations.models import Membership, MembershipRole, Organization


class MembershipListTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.organization = Organization.objects.create(name="Acme")
        self.other_organization = Organization.objects.create(name="Other")

        set_current_organization(self.organization.id)
        self.owner = Membership.objects.create(
            user=User.objects.create_user(email="owner@example.com", password="secret"),
            organization=self.organization, role=MembershipRole.OWNER,
        )
        self.manager = Membership.objects.create(
            user=User.objects.create_user(email="manager@example.com", password="secret"),
            organization=self.organization, role=MembershipRole.SALES_MANAGER,
        )
        self.agent = Membership.objects.create(
            user=User.objects.create_user(email="agent@example.com", password="secret"),
            organization=self.organization, role=MembershipRole.SALES_AGENT,
        )
        self.viewer = Membership.objects.create(
            user=User.objects.create_user(email="viewer@example.com", password="secret"),
            organization=self.organization, role=MembershipRole.VIEWER,
        )
        clear_current_organization()

    def _url(self, **params):
        url = f"/api/v1/organizations/{self.organization.id}/memberships/"
        if params:
            query = "&".join(f"{k}={v}" for k, v in params.items())
            url = f"{url}?{query}"
        return url

    def test_owner_can_list_memberships(self):
        self.client.force_authenticate(user=self.owner.user)
        response = self.client.get(self._url())
        self.assertEqual(response.status_code, 200)
        ids = {m["id"] for m in response.data}
        self.assertEqual(ids, {self.owner.id, self.manager.id, self.agent.id, self.viewer.id})

    def test_admin_can_list_memberships(self):
        set_current_organization(self.organization.id)
        try:
            admin = Membership.objects.create(
                user=User.objects.create_user(email="admin@example.com", password="secret"),
                organization=self.organization, role=MembershipRole.ADMIN,
            )
        finally:
            clear_current_organization()

        self.client.force_authenticate(user=admin.user)
        response = self.client.get(self._url())
        self.assertEqual(response.status_code, 200)

    def test_sales_manager_can_read_but_this_is_org_wide_not_team_scoped(self):
        self.client.force_authenticate(user=self.manager.user)
        response = self.client.get(self._url())
        self.assertEqual(response.status_code, 200)
        ids = {m["id"] for m in response.data}
        self.assertEqual(ids, {self.owner.id, self.manager.id, self.agent.id, self.viewer.id})

    def test_sales_agent_cannot_list_memberships(self):
        self.client.force_authenticate(user=self.agent.user)
        response = self.client.get(self._url())
        self.assertEqual(response.status_code, 403)

    def test_viewer_cannot_list_memberships(self):
        self.client.force_authenticate(user=self.viewer.user)
        response = self.client.get(self._url())
        self.assertEqual(response.status_code, 403)

    def test_filter_by_role(self):
        self.client.force_authenticate(user=self.owner.user)
        response = self.client.get(self._url(role=MembershipRole.SALES_AGENT))
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["id"], self.agent.id)

    def test_is_active_false_surfaces_soft_deleted_members(self):
        set_current_organization(self.organization.id)
        try:
            self.agent.delete()  # soft delete
        finally:
            clear_current_organization()

        self.client.force_authenticate(user=self.owner.user)

        active_response = self.client.get(self._url())
        active_ids = {m["id"] for m in active_response.data}
        self.assertNotIn(self.agent.id, active_ids)

        inactive_response = self.client.get(self._url(is_active="false"))
        inactive_ids = {m["id"] for m in inactive_response.data}
        self.assertEqual(inactive_ids, {self.agent.id})

    def test_other_organization_membership_not_visible(self):
        set_current_organization(self.other_organization.id)
        try:
            Membership.objects.create(
                user=User.objects.create_user(email="stranger@example.com", password="secret"),
                organization=self.other_organization, role=MembershipRole.OWNER,
            )
        finally:
            clear_current_organization()

        self.client.force_authenticate(user=self.owner.user)
        response = self.client.get(self._url())
        ids = {m["id"] for m in response.data}
        self.assertEqual(ids, {self.owner.id, self.manager.id, self.agent.id, self.viewer.id})
