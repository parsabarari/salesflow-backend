from django.test import TestCase

from apps.accounts.models import User
from apps.core.context import clear_current_organization, set_current_organization
from apps.leads.models import Lead, LeadStage
from apps.leads.services import LeadService, LeadStageTransitionService
from apps.organizations.models import Membership, MembershipRole, Organization


class LeadStageTransitionServiceTests(TestCase):
    def setUp(self):
        self.organization = Organization.objects.create(name="Acme")
        set_current_organization(self.organization.id)
        self.owner_membership = Membership.objects.create(
            user=User.objects.create_user(email="owner@example.com", password="secret"),
            organization=self.organization,
            role=MembershipRole.OWNER,
        )
        self.lead = LeadService.create_lead(
            organization=self.organization, owner=self.owner_membership, source="web", email="lead@example.com",
        )

    def tearDown(self):
        clear_current_organization()

    def test_free_movement_between_non_terminal_stages_including_skips(self):
        lead = LeadStageTransitionService.transition(
            lead=self.lead, to_stage=LeadStage.PROPOSAL, changed_by=self.owner_membership,
        )
        self.assertEqual(lead.stage, LeadStage.PROPOSAL)

        lead = LeadStageTransitionService.transition(
            lead=lead, to_stage=LeadStage.CONTACTED, changed_by=self.owner_membership,
        )
        self.assertEqual(lead.stage, LeadStage.CONTACTED)

    def test_lost_requires_reason(self):
        with self.assertRaises(ValueError):
            LeadStageTransitionService.transition(
                lead=self.lead, to_stage=LeadStage.LOST, changed_by=self.owner_membership,
            )

    def test_lost_reopenable_and_clears_reason(self):
        lead = LeadStageTransitionService.transition(
            lead=self.lead, to_stage=LeadStage.LOST, changed_by=self.owner_membership, reason="Budget cut",
        )
        self.assertEqual(lead.lost_reason, "Budget cut")

        lead = LeadStageTransitionService.transition(
            lead=lead, to_stage=LeadStage.QUALIFIED, changed_by=self.owner_membership,
        )
        self.assertEqual(lead.stage, LeadStage.QUALIFIED)
        self.assertIsNone(lead.lost_reason)

    def test_won_is_terminal(self):
        lead = LeadStageTransitionService.transition(
            lead=self.lead, to_stage=LeadStage.WON, changed_by=self.owner_membership,
        )
        with self.assertRaises(ValueError):
            LeadStageTransitionService.transition(
                lead=lead, to_stage=LeadStage.QUALIFIED, changed_by=self.owner_membership,
            )

    def test_every_transition_writes_immutable_history_row(self):
        LeadStageTransitionService.transition(
            lead=self.lead, to_stage=LeadStage.CONTACTED, changed_by=self.owner_membership,
        )
        history = list(self.lead.stage_history.order_by("changed_at"))
        self.assertEqual(len(history), 2)  # creation row + this transition
        self.assertIsNone(history[0].from_stage)
        self.assertEqual(history[0].to_stage, LeadStage.NEW)
        self.assertEqual(history[1].from_stage, LeadStage.NEW)
        self.assertEqual(history[1].to_stage, LeadStage.CONTACTED)
