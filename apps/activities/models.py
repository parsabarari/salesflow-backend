from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.db.models import Q

from apps.core.managers import OrgScopedAllManager, OrgScopedManager, UnscopedManager
from apps.core.models import OrgScopedModel, SoftDeleteModel, TimeStampedModel


class ActivityType(models.TextChoices):
    CALL = "call", "Call"
    MEETING = "meeting", "Meeting"
    FOLLOW_UP = "follow_up", "Follow-up"
    TASK = "task", "Task"
    REMINDER = "reminder", "Reminder"


class ActivityStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    COMPLETED = "completed", "Completed"
    CANCELLED = "cancelled", "Cancelled"


class Activity(TimeStampedModel, SoftDeleteModel, OrgScopedModel):
    Type = ActivityType
    Status = ActivityStatus

    type = models.CharField(max_length=20, choices=Type.choices)

    # Polymorphic parent — Lead or Customer only (Business Rules 8.2,
    # Domain Model §15). The content-type restriction itself isn't
    # expressible as a DB-level constraint against ContentType, so it's
    # enforced in ActivityService (services.py), same rationale already
    # used for Comment/Attachment elsewhere in the project.
    parent_content_type = models.ForeignKey(
        ContentType,
        on_delete=models.PROTECT,
        related_name="+",
    )
    parent_object_id = models.BigIntegerField()
    parent = GenericForeignKey("parent_content_type", "parent_object_id")

    assignee = models.ForeignKey(
        "organizations.Membership",
        on_delete=models.PROTECT,
        related_name="assigned_activities",
    )
    due_date = models.DateTimeField()
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)

    objects = OrgScopedManager()
    all_objects = OrgScopedAllManager()
    unscoped = UnscopedManager()

    class Meta:
        db_table = "activities"
        constraints = [
            models.CheckConstraint(
                condition=Q(type__in=ActivityType.values),
                name="activities_type_valid",
            ),
            models.CheckConstraint(
                condition=Q(status__in=ActivityStatus.values),
                name="activities_status_valid",
            ),
        ]
        indexes = [
            models.Index(
                fields=["parent_content_type", "parent_object_id"],
                name="idx_activities_parent",
            ),
            models.Index(
                fields=["assignee", "due_date"],
                name="idx_activities_assignee_due",
            ),
        ]

    def __str__(self):
        return f"{self.type} due {self.due_date} ({self.status})"
