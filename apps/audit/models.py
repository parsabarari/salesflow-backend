from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models

from apps.core.models import OrgScopedModel, TimeStampedModel
from apps.core.managers import OrgScopedNoSoftDeleteManager, UnscopedManager


class AuditActionType(models.TextChoices):
    MEMBER_INVITED = "member_invited", "Member Invited"
    MEMBER_REMOVED = "member_removed", "Member Removed"
    ROLE_CHANGED = "role_changed", "Role Changed"
    ORG_SETTINGS_CHANGED = "org_settings_changed", "Org Settings Changed"
    OWNERSHIP_TRANSFERRED = "ownership_transferred", "Ownership Transferred"
    HARD_DELETED = "hard_deleted", "Hard Deleted"
    RESTORED = "restored", "Restored"


class AuditLog(TimeStampedModel, OrgScopedModel):
    """Append-only. No soft-delete, no update/delete exposed anywhere
    at the application layer — Domain Model §17 / ERD §18."""

    actor_membership = models.ForeignKey(
        "organizations.Membership",
        on_delete=models.PROTECT,
        related_name="audit_actions",
    )
    action_type = models.CharField(max_length=40, choices=AuditActionType.choices)

    target_content_type = models.ForeignKey(ContentType, on_delete=models.PROTECT)
    target_object_id = models.BigIntegerField()
    target = GenericForeignKey("target_content_type", "target_object_id")

    metadata = models.JSONField(default=dict)

    objects = OrgScopedNoSoftDeleteManager()
    unscoped = UnscopedManager()

    class Meta:
        db_table = "audit_logs"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(action_type__in=AuditActionType.values),
                name="audit_logs_action_type_valid",
            ),
        ]
        indexes = [
            models.Index(fields=["organization", "created_at"], name="idx_audit_logs_org_created"),
        ]

    def __str__(self):
        return f"{self.action_type} by {self.actor_membership_id} @ {self.organization_id}"
    