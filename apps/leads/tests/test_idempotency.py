from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.core.context import clear_current_organization, set_current_organization
from apps.leads.models import LeadStage
from apps.leads.services import LeadService
from apps.organizations.models import Membership, MembershipRole, Organization


class LeadStageIdempotencyTests(TestCase):
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
        clear_current_organization()

    def _url(self):
        return f"/api/v1/organizations/{self.organization.id}/leads/{self.lead.id}/stage/"

    def test_repeated_request_does_not_write_a_second_history_row(self):
        self.client.force_authenticate(user=self.owner.user)
        headers = {"Idempotency-Key": "xyz-789"}

        self.client.post(self._url(), {"to_stage": LeadStage.CONTACTED}, format="json", headers=headers)
        self.client.post(self._url(), {"to_stage": LeadStage.CONTACTED}, format="json", headers=headers)

        set_current_organization(self.organization.id)
        try:
            history_count = self.lead.stage_history.count()
        finally:
            clear_current_organization()

        self.assertEqual(history_count, 2)  # creation row + 1 transition, NOT 3

    def test_different_keys_both_execute(self):
        self.client.force_authenticate(user=self.owner.user)
        self.client.post(self._url(), {"to_stage": LeadStage.CONTACTED}, format="json", headers={"Idempotency-Key": "key-1"})
        self.client.post(self._url(), {"to_stage": LeadStage.QUALIFIED}, format="json", headers={"Idempotency-Key": "key-2"})

        set_current_organization(self.organization.id)
        try:
            self.lead.refresh_from_db()
            self.assertEqual(self.lead.stage, LeadStage.QUALIFIED)
        finally:
            clear_current_organization()

    def test_no_key_always_executes(self):
        self.client.force_authenticate(user=self.owner.user)
        self.client.post(self._url(), {"to_stage": LeadStage.CONTACTED}, format="json")
        self.client.post(self._url(), {"to_stage": LeadStage.QUALIFIED}, format="json")

        set_current_organization(self.organization.id)
        try:
            self.lead.refresh_from_db()
            self.assertEqual(self.lead.stage, LeadStage.QUALIFIED)
        finally:
            clear_current_organization()
