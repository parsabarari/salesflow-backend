from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models

from apps.core.context import get_current_organization
from apps.core.managers import BaseQuerySet


class NotificationType(models.TextChoices):
    # Exactly the trigger list from Business Rules 10.3 / ERD §17.
    LEAD_ASSIGNED = "lead_assigned", "Lead Assigned"
    LEAD_STAGE_CHANGED = "lead_stage_changed", "Lead Stage Changed"
    COMMENT_MENTION = "comment_mention", "Comment Mention"
    TICKET_ASSIGNED = "ticket_assigned", "Ticket Assigned"
    TICKET_STATUS_CHANGED = "ticket_status_changed", "Ticket Status Changed"
    ACTIVITY_DUE_SOON = "activity_due_soon", "Activity Due Soon"
    ACTIVITY_OVERDUE = "activity_overdue", "Activity Overdue"


class NotificationQuerySet(BaseQuerySet):
    def for_current_organization(self):
        from apps.core.context import is_admin_bypass
        if is_admin_bypass():
            return self
        return self.filter(recipient_membership__organization_id=get_current_organization())


class NotificationManager(models.Manager.from_queryset(NotificationQuerySet)):
    def get_queryset(self):
        return super().get_queryset().for_current_organization()


class Notification(models.Model):
    """No deleted_at (Domain Model §16) — a notification is either read
    or unread, not soft-deletable; no organization_id of its own,
    reached via recipient_membership_id, same pattern already used for
    LeadStageHistory and CommentMention."""

    recipient_membership = models.ForeignKey(
        "organizations.Membership", on_delete=models.CASCADE, related_name="notifications"
    )
    type = models.CharField(max_length=40, choices=NotificationType.choices)

    related_content_type = models.ForeignKey(ContentType, on_delete=models.PROTECT, related_name="+")
    related_object_id = models.BigIntegerField()
    related_object = GenericForeignKey("related_content_type", "related_object_id")

    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = NotificationManager()
    unscoped = models.Manager()

    class Meta:
        db_table = "notifications"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(type__in=NotificationType.values),
                name="notifications_type_valid",
            ),
        ]
        indexes = [
            models.Index(
                fields=["recipient_membership", "is_read", "created_at"],
                name="idx_ntf_recipient_read_created",
            ),
        ]

    def __str__(self):
        return f"{self.type} -> {self.recipient_membership_id}"
