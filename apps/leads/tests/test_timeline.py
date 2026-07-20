from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.core.context import clear_current_organization, set_current_organization
from apps.leads.models import LeadStage
from apps.leads.services import LeadService, LeadStageTransitionService
from apps.organizations.models import Membership, MembershipRole, Organization


class LeadTimelineTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.organization = Organization.objects.create(name="Acme")
        set_current_organization(self.organization.id)
        self.owner = Membership.objects.create(
            user=User.objects.create_user(email="owner@example.com", password="secret"),
            organization=self.organization,
            role=MembershipRole.OWNER,
        )
        self.lead = LeadService.create_lead(organization=self.organization, owner=self.owner, source="web", email="lead@example.com")
        LeadStageTransitionService.transition(lead=self.lead, to_stage=LeadStage.CONTACTED, changed_by=self.owner)
        clear_current_organization()

    def test_timeline_includes_creation_and_transition_newest_first(self):
        self.client.force_authenticate(user=self.owner.user)
        response = self.client.get(f"/api/v1/organizations/{self.organization.id}/leads/{self.lead.id}/timeline/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 2)
        self.assertEqual(response.data[0]["data"]["to_stage"], LeadStage.CONTACTED)  # newest first
        self.assertEqual(response.data[1]["data"]["to_stage"], LeadStage.NEW)
