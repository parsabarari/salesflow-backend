import re

from django.contrib.contenttypes.models import ContentType
from django.core.files.storage import default_storage
from django.db import transaction

from apps.collaboration.models import Attachment, Comment, CommentMention
from apps.core.services import resolve_polymorphic_parent
from apps.customers.models import Customer
from apps.leads.models import Lead
from apps.organizations.models import Membership
from apps.tickets.models import Ticket

COMMENT_PARENT_MODEL_MAP = {
    "lead": Lead,
    "customer": Customer,
    "ticket": Ticket,
}

ATTACHMENT_PARENT_MODEL_MAP = {
    "lead": Lead,
    "customer": Customer,
}

MENTION_PATTERN = re.compile(r"@([\w.+-]+@[\w.-]+\.\w+)")


class CommentService:
    @staticmethod
    @transaction.atomic
    def create(*, organization, parent_type: str, parent_id: int, author, body: str) -> Comment:
        parent = resolve_polymorphic_parent(
            model_map=COMMENT_PARENT_MODEL_MAP,
            parent_type=parent_type,
            parent_id=parent_id,
            organization_id=organization.id,
        )
        content_type = ContentType.objects.get_for_model(parent.__class__)
        comment = Comment.objects.create(
            organization=organization,
            parent_content_type=content_type,
            parent_object_id=parent.id,
            author=author,
            body=body,
        )
        CommentService._sync_mentions(comment)
        return comment

    @staticmethod
    @transaction.atomic
    def update_body(comment: Comment, body: str) -> Comment:
        comment.body = body
        comment.save(update_fields=["body"])
        CommentMention.objects.filter(comment=comment).delete()
        CommentService._sync_mentions(comment)
        return comment

    @staticmethod
    def _sync_mentions(comment: Comment) -> None:
        emails = set(MENTION_PATTERN.findall(comment.body))
        if not emails:
            return
        members = Membership.objects.filter(user__email__in=emails, deleted_at__isnull=True)
        CommentMention.objects.bulk_create(
            [CommentMention(comment=comment, mentioned_membership=member) for member in members]
        )


class AttachmentService:
    @staticmethod
    def create(*, organization, parent_type: str, parent_id: int, uploaded_by, uploaded_file) -> Attachment:
        parent = resolve_polymorphic_parent(
            model_map=ATTACHMENT_PARENT_MODEL_MAP,
            parent_type=parent_type,
            parent_id=parent_id,
            organization_id=organization.id,
        )
        content_type = ContentType.objects.get_for_model(parent.__class__)
        # Namespaced by organization_id so two tenants' files never
        # collide in the same bucket, even with an identical filename —
        # AWS_S3_FILE_OVERWRITE=False (settings, previous chunk) also
        # protects against collisions within the same org.
        storage_key = default_storage.save(f"attachments/{organization.id}/{uploaded_file.name}", uploaded_file)
        return Attachment.objects.create(
            organization=organization,
            parent_content_type=content_type,
            parent_object_id=parent.id,
            uploaded_by=uploaded_by,
            file_reference=storage_key,
            original_filename=uploaded_file.name,
            file_size_bytes=uploaded_file.size,
        )

    @staticmethod
    def get_signed_url(attachment: Attachment) -> str:
        return default_storage.url(attachment.file_reference)
