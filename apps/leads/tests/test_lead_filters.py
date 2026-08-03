from datetime import timedelta

from django.test import TestCase
from django.utils import timezone
from django.utils.dateparse import parse_datetime  
from urllib.parse import urlencode
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.core.context import clear_current_organization, set_current_organization
from apps.leads.models import LeadStage, Tag
from apps.leads.services import LeadService, LeadStageTransitionService, TagService
from apps.organizations.models import Membership, MembershipRole, Organization


class LeadListFilterTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.organization = Organization.objects.create(name="Acme")
        set_current_organization(self.organization.id)
        self.owner = Membership.objects.create(
            user=User.objects.create_user(email="owner@example.com", password="secret"),
            organization=self.organization, role=MembershipRole.OWNER,
        )
        self.other_owner = Membership.objects.create(
            user=User.objects.create_user(email="owner2@example.com", password="secret"),
            organization=self.organization, role=MembershipRole.OWNER,
        )

        self.lead_new = LeadService.create_lead(
            organization=self.organization, owner=self.owner, source="web", email="new@example.com",
        )
        self.lead_won = LeadService.create_lead(
            organization=self.organization, owner=self.owner, source="referral", email="won@example.com",
        )
        LeadStageTransitionService.transition(lead=self.lead_won, to_stage=LeadStage.WON, changed_by=self.owner)

        self.lead_other_owner = LeadService.create_lead(
            organization=self.organization, owner=self.other_owner, source="web", email="other@example.com",
        )

        self.tag = TagService.create(organization=self.organization, name="hot")
        TagService.attach(lead=self.lead_new, tag=self.tag)
        clear_current_organization()

    def _url(self, **params):
        url = f"/api/v1/organizations/{self.organization.id}/leads/"
        if params:
            url = f"{url}?{urlencode(params)}"
        return url

    def test_filter_by_stage(self):
        self.client.force_authenticate(user=self.owner.user)
        response = self.client.get(self._url(stage=LeadStage.WON))
        ids = {lead["id"] for lead in response.data}
        self.assertEqual(ids, {self.lead_won.id})

    def test_filter_by_owner(self):
        self.client.force_authenticate(user=self.owner.user)
        response = self.client.get(self._url(owner=self.other_owner.id))
        ids = {lead["id"] for lead in response.data}
        self.assertEqual(ids, {self.lead_other_owner.id})

    def test_filter_by_source(self):
        self.client.force_authenticate(user=self.owner.user)
        response = self.client.get(self._url(source="referral"))
        ids = {lead["id"] for lead in response.data}
        self.assertEqual(ids, {self.lead_won.id})

    def test_filter_by_tags(self):
        self.client.force_authenticate(user=self.owner.user)
        response = self.client.get(self._url(tags=self.tag.id))
        ids = {lead["id"] for lead in response.data}
        self.assertEqual(ids, {self.lead_new.id})

    def test_filter_by_created_at_range(self):
        self.client.force_authenticate(user=self.owner.user)
        future_start = (timezone.now() + timedelta(days=1)).isoformat()
        response = self.client.get(self._url(**{"created_at__gte": future_start}))
        self.assertEqual(response.data, [])

        past_start = (timezone.now() - timedelta(days=1)).isoformat()
        response = self.client.get(self._url(**{"created_at__gte": past_start}))
        ids = {lead["id"] for lead in response.data}
        self.assertEqual(ids, {self.lead_new.id, self.lead_won.id, self.lead_other_owner.id})

    def test_ordering_by_created_at_descending(self):
        self.client.force_authenticate(user=self.owner.user)
        response = self.client.get(self._url(ordering="-created_at"))
        ids = [lead["id"] for lead in response.data]
        # lead_other_owner was created last among owner's visible set
        # (Owner sees all leads — SCOPE_FULL), so newest-first puts it first.
        self.assertEqual(ids[0], self.lead_other_owner.id)

    def test_is_archived_true_returns_only_archived(self):
        set_current_organization(self.organization.id)
        try:
            self.lead_new.is_archived = True
            self.lead_new.save(update_fields=["is_archived"])
        finally:
            clear_current_organization()

        self.client.force_authenticate(user=self.owner.user)
        response = self.client.get(self._url(is_archived="true"))
        ids = {lead["id"] for lead in response.data}
        self.assertEqual(ids, {self.lead_new.id})

        default_response = self.client.get(self._url())
        default_ids = {lead["id"] for lead in default_response.data}
        self.assertNotIn(self.lead_new.id, default_ids)

    def test_combined_filters(self):
        self.client.force_authenticate(user=self.owner.user)
        response = self.client.get(self._url(stage=LeadStage.WON, owner=self.owner.id))
        ids = {lead["id"] for lead in response.data}
        self.assertEqual(ids, {self.lead_won.id})
