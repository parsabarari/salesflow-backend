from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.activities.services import ActivityService
from apps.core.context import clear_current_organization, set_current_organization
from apps.core.redis_client import get_redis_client
from apps.customers.models import Customer, CustomerType
from apps.dashboard.services import CACHE_KEY_PREFIX
from apps.leads.models import LeadStage
from apps.leads.services import LeadService, LeadStageTransitionService
from apps.organizations.models import Membership, MembershipRole, Organization
from apps.tickets.services import TicketService
from django.utils import timezone
from datetime import timedelta


class DashboardSummaryTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.redis = get_redis_client()
        for key in self.redis.scan_iter(f"{CACHE_KEY_PREFIX}*"):
            self.redis.delete(key)

        self.organization = Organization.objects.create(name="Acme")
        set_current_organization(self.organization.id)
        self.owner = Membership.objects.create(
            user=User.objects.create_user(email="owner@example.com", password="secret"),
            organization=self.organization,
            role=MembershipRole.OWNER,
        )
        self.agent = Membership.objects.create(
            user=User.objects.create_user(email="agent@example.com", password="secret"),
            organization=self.organization,
            role=MembershipRole.SALES_AGENT,
        )
        clear_current_organization()

    def _url(self):
        return f"/api/v1/organizations/{self.organization.id}/dashboard/summary/"

    def test_empty_org_returns_zeroed_summary(self):
        self.client.force_authenticate(user=self.owner.user)
        response = self.client.get(self._url())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["total_leads"], 0)
        self.assertEqual(response.data["conversion_rate"], 0.0)
        self.assertEqual(response.data["open_tickets_count"], 0)
        self.assertEqual(response.data["upcoming_activities"], [])

    def test_lead_counts_by_stage(self):
        set_current_organization(self.organization.id)
        LeadService.create_lead(organization=self.organization, owner=self.owner, source="web", email="a@example.com")
        LeadService.create_lead(organization=self.organization, owner=self.owner, source="web", email="b@example.com")
        clear_current_organization()

        self.client.force_authenticate(user=self.owner.user)
        response = self.client.get(self._url())
        self.assertEqual(response.data["lead_counts_by_stage"][LeadStage.NEW], 2)
        self.assertEqual(response.data["total_leads"], 2)

    def test_conversion_rate_computed_from_won_and_lost_only(self):
        set_current_organization(self.organization.id)
        won_lead = LeadService.create_lead(organization=self.organization, owner=self.owner, source="web", email="won@example.com")
        lost_lead = LeadService.create_lead(organization=self.organization, owner=self.owner, source="web", email="lost@example.com")
        LeadService.create_lead(organization=self.organization, owner=self.owner, source="web", email="active@example.com")

        LeadStageTransitionService.transition(lead=won_lead, to_stage=LeadStage.WON, changed_by=self.owner)
        LeadStageTransitionService.transition(lead=lost_lead, to_stage=LeadStage.LOST, changed_by=self.owner, reason="Budget")
        clear_current_organization()

        self.client.force_authenticate(user=self.owner.user)
        response = self.client.get(self._url())
        # 1 won / (1 won + 1 lost) = 0.5 — the still-active third lead
        # is excluded from the denominator entirely.
        self.assertEqual(response.data["conversion_rate"], 0.5)

    def test_open_tickets_count_excludes_resolved_and_closed(self):
        set_current_organization(self.organization.id)
        customer = Customer.objects.create(organization=self.organization, type=CustomerType.INDIVIDUAL, name="Jane", email="jane@example.com")
        open_ticket = TicketService.create(
            organization=self.organization, customer=customer, contact=None,
            subject="Open issue", priority="medium", assignee=None, created_by=self.owner,
        )
        resolved_ticket = TicketService.create(
            organization=self.organization, customer=customer, contact=None,
            subject="Resolved issue", priority="medium", assignee=None, created_by=self.owner,
        )
        TicketService.transition_status(resolved_ticket, "in_progress")
        TicketService.transition_status(resolved_ticket, "resolved")
        clear_current_organization()

        self.client.force_authenticate(user=self.owner.user)
        response = self.client.get(self._url())
        self.assertEqual(response.data["open_tickets_count"], 1)

    def test_upcoming_activities_excludes_completed_and_past(self):
        set_current_organization(self.organization.id)
        lead = LeadService.create_lead(organization=self.organization, owner=self.owner, source="web", email="lead@example.com")
        upcoming = ActivityService.create(
            organization=self.organization, parent_type="lead", parent_id=lead.id,
            assignee=self.owner, activity_type="call", due_date=timezone.now() + timedelta(days=1),
        )
        past = ActivityService.create(
            organization=self.organization, parent_type="lead", parent_id=lead.id,
            assignee=self.owner, activity_type="call", due_date=timezone.now() - timedelta(days=1),
        )
        completed = ActivityService.create(
            organization=self.organization, parent_type="lead", parent_id=lead.id,
            assignee=self.owner, activity_type="call", due_date=timezone.now() + timedelta(days=2),
        )
        ActivityService.update_status(completed, "completed")
        clear_current_organization()

        self.client.force_authenticate(user=self.owner.user)
        response = self.client.get(self._url())
        upcoming_ids = {a["id"] for a in response.data["upcoming_activities"]}
        self.assertEqual(upcoming_ids, {upcoming.id})

    def test_response_is_cached_across_requests(self):
        set_current_organization(self.organization.id)
        LeadService.create_lead(organization=self.organization, owner=self.owner, source="web", email="a@example.com")
        clear_current_organization()

        self.client.force_authenticate(user=self.owner.user)
        first_response = self.client.get(self._url())
        self.assertEqual(first_response.data["total_leads"], 1)

        # A second Lead created after the first request should NOT show
        # up in the second request's response — Architecture doc §4's
        # 60s cache means this is expected staleness, not a bug.
        set_current_organization(self.organization.id)
        LeadService.create_lead(organization=self.organization, owner=self.owner, source="web", email="b@example.com")
        clear_current_organization()

        second_response = self.client.get(self._url())
        self.assertEqual(second_response.data["total_leads"], 1)  # still cached, not 2

    def test_any_authenticated_member_can_read(self):
        set_current_organization(self.organization.id)
        LeadService.create_lead(organization=self.organization, owner=self.owner, source="web", email="a@example.com")
        clear_current_organization()

        self.client.force_authenticate(user=self.agent.user)
        response = self.client.get(self._url())
        self.assertEqual(response.status_code, 200)
