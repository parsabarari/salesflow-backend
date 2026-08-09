from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.core.context import clear_current_organization, set_current_organization
from apps.organizations.models import Membership, MembershipRole, Organization


class MembershipRestoreTests(TestCase):
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
        self.agent.delete()  # soft-delete = "removed" member
        clear_current_organization()

    def _url(self, membership_id):
        return f"/api/v1/organizations/{self.organization.id}/memberships/{membership_id}/restore/"

    def test_owner_can_restore_removed_member(self):
        self.client.force_authenticate(user=self.owner.user)
        response = self.client.post(self._url(self.agent.id))
        self.assertEqual(response.status_code, 200)

        set_current_organization(self.organization.id)
        try:
            self.agent.refresh_from_db()
        finally:
            clear_current_organization()
        self.assertIsNone(self.agent.deleted_at)

    def test_restoring_active_membership_returns_404(self):
        self.client.force_authenticate(user=self.owner.user)
        response = self.client.post(self._url(self.owner.id))  # owner is active, never deleted
        self.assertEqual(response.status_code, 404)
