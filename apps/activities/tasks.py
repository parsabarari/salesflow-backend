from datetime import timedelta

from celery import shared_task
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone

from apps.activities.models import Activity, ActivityStatus
from apps.core.context import clear_current_organization, set_current_organization
from apps.notifications.models import Notification, NotificationType
from apps.notifications.services import NotificationService
from apps.organizations.models import Organization


@shared_task
def activity_due_soon_and_overdue_sweep_task():
    now = timezone.now()
    soon_threshold = now + timedelta(hours=24)
    activity_content_type = ContentType.objects.get_for_model(Activity)

    for organization in Organization.objects.filter(deleted_at__isnull=True):
        set_current_organization(organization.id)
        try:
            pending = Activity.objects.filter(status=ActivityStatus.PENDING)

            for activity in pending.filter(due_date__gt=now, due_date__lte=soon_threshold):
                _notify_once(activity, NotificationType.ACTIVITY_DUE_SOON, activity_content_type)

            for activity in pending.filter(due_date__lte=now):
                _notify_once(activity, NotificationType.ACTIVITY_OVERDUE, activity_content_type)
        finally:
            clear_current_organization()


def _notify_once(activity, notification_type, content_type):
    already_sent = Notification.unscoped.filter(
        related_content_type=content_type,
        related_object_id=activity.id,
        type=notification_type,
        recipient_membership=activity.assignee,
    ).exists()
    if already_sent:
        return
    NotificationService.create(
        recipient_membership=activity.assignee, notification_type=notification_type, related_object=activity,
    )
