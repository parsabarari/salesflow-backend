from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.core.context import clear_current_organization, set_current_organization
from apps.leads.services import LeadService, TagService
from apps.organizations.models import Membership, MembershipRole, Organization


class LeadRestoreTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.organization = Organization.objects.create(name="Acme")
        set_current_organization(self.organization.id)
        self.owner = Membership.objects.create(
            user=User.objects.create_user(email="owner@example.com", password="secret"),
            organization=self.organization, role=MembershipRole.OWNER,
        )
        self.admin = Membership.objects.create(
            user=User.objects.create_user(email="admin@example.com", password="secret"),
            organization=self.organization, role=MembershipRole.ADMIN,
        )
        self.agent = Membership.objects.create(
            user=User.objects.create_user(email="agent@example.com", password="secret"),
            organization=self.organization, role=MembershipRole.SALES_AGENT,
        )
        self.lead = LeadService.create_lead(
            organization=self.organization, owner=self.agent, source="web", email="lead@example.com",
        )
        self.lead.delete()  # soft delete
        clear_current_organization()

    def _url(self, lead_id, organization_id=None):
        return f"/api/v1/organizations/{organization_id or self.organization.id}/leads/{lead_id}/restore/"

    def test_owner_can_restore(self):
        self.client.force_authenticate(user=self.owner.user)
        response = self.client.post(self._url(self.lead.id))
        self.assertEqual(response.status_code, 200)

        set_current_organization(self.organization.id)
        try:
            self.lead.refresh_from_db()
        finally:
            clear_current_organization()
        self.assertIsNone(self.lead.deleted_at)

    def test_admin_can_restore(self):
        self.client.force_authenticate(user=self.admin.user)
        response = self.client.post(self._url(self.lead.id))
        self.assertEqual(response.status_code, 200)

    def test_sales_agent_cannot_restore(self):
        self.client.force_authenticate(user=self.agent.user)
        response = self.client.post(self._url(self.lead.id))
        self.assertEqual(response.status_code, 403)

    def test_restoring_already_active_lead_returns_404(self):
        set_current_organization(self.organization.id)
        try:
            self.lead.restore()
        finally:
            clear_current_organization()

        self.client.force_authenticate(user=self.owner.user)
        response = self.client.post(self._url(self.lead.id))
        self.assertEqual(response.status_code, 404)

    def test_nonexistent_lead_returns_404(self):
        self.client.force_authenticate(user=self.owner.user)
        response = self.client.post(self._url(999999))
        self.assertEqual(response.status_code, 404)

    def test_restore_scoped_to_organization(self):
        other_organization = Organization.objects.create(name="Other")
        set_current_organization(other_organization.id)
        try:
            stranger = Membership.objects.create(
                user=User.objects.create_user(email="stranger@example.com", password="secret"),
                organization=other_organization, role=MembershipRole.OWNER,
            )
        finally:
            clear_current_organization()

        self.client.force_authenticate(user=stranger.user)
        response = self.client.post(self._url(self.lead.id, organization_id=other_organization.id))
        self.assertEqual(response.status_code, 404)


class TagRestoreTests(TestCase):
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
        self.tag = TagService.create(organization=self.organization, name="hot")
        self.tag.delete()
        clear_current_organization()

    def _url(self, tag_id):
        return f"/api/v1/organizations/{self.organization.id}/tags/{tag_id}/restore/"

    def test_owner_can_restore_tag(self):
        self.client.force_authenticate(user=self.owner.user)
        response = self.client.post(self._url(self.tag.id))
        self.assertEqual(response.status_code, 200)

    def test_sales_agent_cannot_restore_tag(self):
        self.client.force_authenticate(user=self.agent.user)
        response = self.client.post(self._url(self.tag.id))
        self.assertEqual(response.status_code, 403)
