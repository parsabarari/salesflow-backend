from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from apps.accounts.models import User
from apps.activities.services import ActivityService
from apps.activities.tasks import activity_due_soon_and_overdue_sweep_task
from apps.core.context import clear_current_organization, set_current_organization
from apps.leads.models import Lead
from apps.notifications.models import Notification, NotificationType
from apps.organizations.models import Membership, MembershipRole, Organization


class ActivityNotificationSweepTests(TestCase):
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

    def tearDown(self):
        clear_current_organization()

    def test_due_within_24h_gets_due_soon_notification(self):
        due_soon_activity = ActivityService.create(
            organization=self.organization, parent_type="lead", parent_id=self.lead.id,
            assignee=self.owner, activity_type="task", due_date=timezone.now() + timedelta(hours=12),
        )
        activity_due_soon_and_overdue_sweep_task()

        self.assertTrue(
            Notification.unscoped.filter(
                recipient_membership=self.owner, type=NotificationType.ACTIVITY_DUE_SOON,
                related_object_id=due_soon_activity.id,
            ).exists()
        )

    def test_past_due_date_gets_overdue_notification(self):
        overdue_activity = ActivityService.create(
            organization=self.organization, parent_type="lead", parent_id=self.lead.id,
            assignee=self.owner, activity_type="task", due_date=timezone.now() - timedelta(hours=1),
        )
        activity_due_soon_and_overdue_sweep_task()

        self.assertTrue(
            Notification.unscoped.filter(
                recipient_membership=self.owner, type=NotificationType.ACTIVITY_OVERDUE,
                related_object_id=overdue_activity.id,
            ).exists()
        )

    def test_far_future_due_date_gets_no_notification(self):
        far_future_activity = ActivityService.create(
            organization=self.organization, parent_type="lead", parent_id=self.lead.id,
            assignee=self.owner, activity_type="task", due_date=timezone.now() + timedelta(days=5),
        )
        activity_due_soon_and_overdue_sweep_task()

        self.assertFalse(
            Notification.unscoped.filter(related_object_id=far_future_activity.id).exists()
        )

    def test_sweep_does_not_duplicate_notification_on_repeated_run(self):
        """Business Rules 8.3: fires once, not repeatedly, even though
        the sweep itself runs every 15 minutes indefinitely."""
        overdue_activity = ActivityService.create(
            organization=self.organization, parent_type="lead", parent_id=self.lead.id,
            assignee=self.owner, activity_type="task", due_date=timezone.now() - timedelta(hours=1),
        )
        activity_due_soon_and_overdue_sweep_task()
        activity_due_soon_and_overdue_sweep_task()
        activity_due_soon_and_overdue_sweep_task()

        count = Notification.unscoped.filter(
            recipient_membership=self.owner, type=NotificationType.ACTIVITY_OVERDUE,
            related_object_id=overdue_activity.id,
        ).count()
        self.assertEqual(count, 1)

    def test_completed_activity_not_swept(self):
        activity = ActivityService.create(
            organization=self.organization, parent_type="lead", parent_id=self.lead.id,
            assignee=self.owner, activity_type="task", due_date=timezone.now() - timedelta(hours=1),
        )
        ActivityService.update_status(activity, "completed")
        activity_due_soon_and_overdue_sweep_task()

        self.assertFalse(Notification.unscoped.filter(related_object_id=activity.id).exists())
