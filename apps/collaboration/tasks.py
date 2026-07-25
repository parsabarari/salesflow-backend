from celery import shared_task
from django.conf import settings
from django.core.mail import send_mail

from apps.collaboration.models import Comment
from apps.organizations.models import Membership


@shared_task
def send_mention_email_task(comment_id, mentioned_membership_id):
    try:
        comment = Comment.unscoped.get(id=comment_id)
    except Comment.DoesNotExist:
        return
    try:
        membership = Membership.unscoped.get(id=mentioned_membership_id)
    except Membership.DoesNotExist:
        return

    parent = comment.parent  # GenericForeignKey resolution
    parent_label = f"{comment.parent_content_type.model} #{comment.parent_object_id}" if parent is None else str(parent)

    send_mail(
        subject="You were mentioned in a comment",
        message=f"You were mentioned in a comment on {parent_label}:\n\n{comment.body}",
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[membership.user.email],
    )
