from django.test import TestCase

from apps.accounts.models import User
from apps.activities.models import Activity, ActivityStatus, ActivityType
from apps.activities.services import ActivityService
from apps.core.context import clear_current_organization, set_current_organization
from apps.leads.models import Lead
from apps.organizations.models import Membership, MembershipRole, Organization


class ActivityStatusTransitionTests(TestCase):
    """Business Rules 8.1: Pending -> Completed / Cancelled only; both
    are terminal end states."""

    def setUp(self):
        self.organization = Organization.objects.create(name="Acme")
        set_current_organization(self.organization.id)
        self.owner = Membership.objects.create(
            user=User.objects.create_user(email="owner@example.com", password="secret"),
            organization=self.organization,
            role=MembershipRole.OWNER,
        )
        self.lead = Lead.objects.create(
            organization=self.organization, owner=self.owner, source="web", email="lead@example.com"
        )
        self.activity = ActivityService.create(
            organization=self.organization,
            parent_type="lead",
            parent_id=self.lead.id,
            assignee=self.owner,
            activity_type=ActivityType.TASK,
            due_date="2026-08-01T10:00:00Z",
        )
        clear_current_organization()

    def test_pending_can_transition_to_completed(self):
        ActivityService.update_status(self.activity, ActivityStatus.COMPLETED)
        self.activity.refresh_from_db()
        self.assertEqual(self.activity.status, ActivityStatus.COMPLETED)

    def test_pending_can_transition_to_cancelled(self):
        ActivityService.update_status(self.activity, ActivityStatus.CANCELLED)
        self.activity.refresh_from_db()
        self.assertEqual(self.activity.status, ActivityStatus.CANCELLED)

    def test_completed_cannot_transition_again(self):
        ActivityService.update_status(self.activity, ActivityStatus.COMPLETED)
        with self.assertRaises(ValueError):
            ActivityService.update_status(self.activity, ActivityStatus.CANCELLED)

    def test_cancelled_cannot_transition_again(self):
        ActivityService.update_status(self.activity, ActivityStatus.CANCELLED)
        with self.assertRaises(ValueError):
            ActivityService.update_status(self.activity, ActivityStatus.COMPLETED)

    def test_invalid_target_status_rejected(self):
        with self.assertRaises(ValueError):
            ActivityService.update_status(self.activity, ActivityStatus.PENDING)
