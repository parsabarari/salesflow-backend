from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models

from apps.core.context import get_current_organization
from apps.core.managers import BaseQuerySet, OrgScopedAllManager, OrgScopedManager, UnscopedManager
from apps.core.models import OrgScopedModel, SoftDeleteModel, TimeStampedModel


class Comment(TimeStampedModel, SoftDeleteModel, OrgScopedModel):
    """Covers both 'Notes' and 'Internal notes' per the Domain Model §1
    unification decision — there is no separate Note model. Allowed
    parent types (Lead/Customer/Ticket, Business Rules 9.1) are
    enforced in CommentService, same rationale as Activity's parent
    restriction: ContentType has no DB-level way to restrict which
    content types are valid for a given FK."""

    parent_content_type = models.ForeignKey(ContentType, on_delete=models.PROTECT, related_name="+")
    parent_object_id = models.BigIntegerField()
    parent = GenericForeignKey("parent_content_type", "parent_object_id")

    author = models.ForeignKey("organizations.Membership", on_delete=models.PROTECT, related_name="comments")
    body = models.TextField()

    objects = OrgScopedManager()
    all_objects = OrgScopedAllManager()
    unscoped = UnscopedManager()

    class Meta:
        db_table = "comments"
        indexes = [
            models.Index(
                fields=["parent_content_type", "parent_object_id", "created_at"],
                name="idx_comments_parent_created",
            ),
        ]

    def __str__(self):
        return f"Comment #{self.pk} by {self.author_id}"


class CommentMentionQuerySet(BaseQuerySet):
    def for_current_organization(self):
        from apps.core.context import is_admin_bypass
        if is_admin_bypass():
            return self
        return self.filter(comment__organization_id=get_current_organization())


class CommentMentionManager(models.Manager.from_queryset(CommentMentionQuerySet)):
    """CommentMention has no organization_id of its own (ERD §14) —
    same 'reachable only through the parent' situation already handled
    for LeadStageHistory in apps/leads/models.py."""

    def get_queryset(self):
        return super().get_queryset().for_current_organization()


class CommentMention(models.Model):
    """No deleted_at (ERD §14) — mentions aren't independently
    soft-deletable; they live and die with their parent Comment."""

    comment = models.ForeignKey(Comment, on_delete=models.CASCADE, related_name="mentions")
    mentioned_membership = models.ForeignKey(
        "organizations.Membership", on_delete=models.CASCADE, related_name="comment_mentions"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    objects = CommentMentionManager()
    unscoped = models.Manager()

    class Meta:
        db_table = "comment_mentions"
        indexes = [
            models.Index(fields=["mentioned_membership", "created_at"], name="idx_cm_membership_created"),
        ]

    def __str__(self):
        return f"Mention of {self.mentioned_membership_id} in comment #{self.comment_id}"


class Attachment(TimeStampedModel, SoftDeleteModel, OrgScopedModel):
    """Parent restricted to Lead/Customer only (Domain Model §13 —
    Tickets don't get Attachments per PRD 5.8), enforced in
    AttachmentService, same pattern as Activity/Comment above."""

    parent_content_type = models.ForeignKey(ContentType, on_delete=models.PROTECT, related_name="+")
    parent_object_id = models.BigIntegerField()
    parent = GenericForeignKey("parent_content_type", "parent_object_id")

    uploaded_by = models.ForeignKey("organizations.Membership", on_delete=models.PROTECT, related_name="attachments")
    file_reference = models.CharField(max_length=500)
    original_filename = models.CharField(max_length=255)
    file_size_bytes = models.BigIntegerField()

    objects = OrgScopedManager()
    all_objects = OrgScopedAllManager()
    unscoped = UnscopedManager()

    class Meta:
        db_table = "attachments"
        constraints = [
            models.CheckConstraint(condition=models.Q(file_size_bytes__gte=0), name="attachments_size_non_negative"),
        ]
        indexes = [
            models.Index(fields=["parent_content_type", "parent_object_id"], name="idx_attachments_parent"),
        ]

    def __str__(self):
        return self.original_filename
