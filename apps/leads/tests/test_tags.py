from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.core.context import clear_current_organization, set_current_organization
from apps.leads.models import Tag
from apps.leads.services import LeadService
from apps.organizations.models import Membership, MembershipRole, Organization


class TagTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.organization = Organization.objects.create(name="Acme")
        set_current_organization(self.organization.id)
        self.owner = Membership.objects.create(user=User.objects.create_user(email="owner@example.com", password="secret"), organization=self.organization, role=MembershipRole.OWNER)
        self.agent = Membership.objects.create(user=User.objects.create_user(email="agent@example.com", password="secret"), organization=self.organization, role=MembershipRole.SALES_AGENT)
        self.lead = LeadService.create_lead(organization=self.organization, owner=self.agent, source="web", email="lead@example.com")
        self.tag = Tag.objects.create(organization=self.organization, name="hot")
        clear_current_organization()

    def _tags_url(self):
        return f"/api/v1/organizations/{self.organization.id}/tags/"

    def test_owner_can_create_tag(self):
        self.client.force_authenticate(user=self.owner.user)
        response = self.client.post(self._tags_url(), {"name": "urgent"}, format="json")
        self.assertEqual(response.status_code, 201)

    def test_sales_agent_cannot_create_tag(self):
        self.client.force_authenticate(user=self.agent.user)
        response = self.client.post(self._tags_url(), {"name": "urgent"}, format="json")
        self.assertEqual(response.status_code, 403)

    def test_anyone_can_list_tags(self):
        self.client.force_authenticate(user=self.agent.user)
        response = self.client.get(self._tags_url())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)

    def test_agent_can_attach_tag_to_own_lead(self):
        self.client.force_authenticate(user=self.agent.user)
        url = f"/api/v1/organizations/{self.organization.id}/leads/{self.lead.id}/tags/"
        response = self.client.post(url, {"tag_id": self.tag.id}, format="json")
        self.assertEqual(response.status_code, 204)

        set_current_organization(self.organization.id)
        try:
            self.assertEqual(self.lead.tags.count(), 1)
        finally:
            clear_current_organization()

    def test_agent_cannot_attach_tag_to_others_lead(self):
        other_agent = Membership.objects.create(
            user=User.objects.create_user(email="other@example.com", password="secret"),
            organization=self.organization,
            role=MembershipRole.SALES_AGENT,
        )
        self.client.force_authenticate(user=other_agent.user)
        url = f"/api/v1/organizations/{self.organization.id}/leads/{self.lead.id}/tags/"
        response = self.client.post(url, {"tag_id": self.tag.id}, format="json")
        self.assertEqual(response.status_code, 404)  # not visible in other_agent's own-only scope

    def test_detach_tag(self):
        self.client.force_authenticate(user=self.agent.user)
        attach_url = f"/api/v1/organizations/{self.organization.id}/leads/{self.lead.id}/tags/"
        self.client.post(attach_url, {"tag_id": self.tag.id}, format="json")

        detach_url = f"/api/v1/organizations/{self.organization.id}/leads/{self.lead.id}/tags/{self.tag.id}/"
        response = self.client.delete(detach_url)
        self.assertEqual(response.status_code, 204)

        set_current_organization(self.organization.id)
        try:
            self.assertEqual(self.lead.tags.count(), 0)
        finally:
            clear_current_organization()
