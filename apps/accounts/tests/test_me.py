from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.core.context import clear_current_organization, set_current_organization
from apps.organizations.models import Membership, MembershipRole, Organization


class MeEndpointTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(email="member@example.com", password="secret")

        self.organization_a = Organization.objects.create(name="Acme")
        self.organization_b = Organization.objects.create(name="Beta")

        set_current_organization(self.organization_a.id)
        self.membership_a = Membership.objects.create(
            user=self.user, organization=self.organization_a, role=MembershipRole.OWNER,
        )
        clear_current_organization()

        set_current_organization(self.organization_b.id)
        self.membership_b = Membership.objects.create(
            user=self.user, organization=self.organization_b, role=MembershipRole.SALES_AGENT,
        )
        clear_current_organization()

    def _url(self):
        return "/api/v1/auth/me/"

    def test_unauthenticated_request_rejected(self):
        response = self.client.get(self._url())
        self.assertEqual(response.status_code, 401)

    def test_returns_user_identity_fields(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.get(self._url())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["user_id"], self.user.id)
        self.assertEqual(response.data["email"], self.user.email)
        self.assertIn("is_email_verified", response.data)

    def test_returns_all_memberships_across_organizations(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.get(self._url())

        returned = {(m["organization_id"], m["role"]) for m in response.data["memberships"]}
        self.assertEqual(
            returned,
            {
                (self.organization_a.id, MembershipRole.OWNER),
                (self.organization_b.id, MembershipRole.SALES_AGENT),
            },
        )

    def test_membership_ids_present_for_client_discovery(self):
        # This is the whole point of the endpoint (known gap being closed):
        # a client must be able to discover membership_id/organization_id
        # without already having them from a signup/invitation response.
        self.client.force_authenticate(user=self.user)
        response = self.client.get(self._url())

        membership_ids = {m["membership_id"] for m in response.data["memberships"]}
        self.assertEqual(membership_ids, {self.membership_a.id, self.membership_b.id})

    def test_soft_deleted_membership_excluded(self):
        set_current_organization(self.organization_b.id)
        try:
            self.membership_b.delete()  # soft delete
        finally:
            clear_current_organization()

        self.client.force_authenticate(user=self.user)
        response = self.client.get(self._url())

        org_ids = {m["organization_id"] for m in response.data["memberships"]}
        self.assertEqual(org_ids, {self.organization_a.id})

    def test_user_with_no_memberships_returns_empty_list(self):
        lone_user = User.objects.create_user(email="lonely@example.com", password="secret")
        self.client.force_authenticate(user=lone_user)
        response = self.client.get(self._url())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["memberships"], [])
