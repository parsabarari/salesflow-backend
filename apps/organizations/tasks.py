# apps/organizations/tasks.py
from celery import shared_task
from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone

from apps.organizations.models import Invitation


@shared_task
def send_invitation_email_task(invitation_id):
    try:
        invitation = Invitation.unscoped.get(id=invitation_id)
    except Invitation.DoesNotExist:
        return
    accept_url = f"{settings.FRONTEND_BASE_URL}/accept-invite?token={invitation.token}"
    send_mail(
        subject="You've been invited",
        message=f"Click to join: {accept_url}",
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[invitation.email],
    )


@shared_task
def expire_pending_invitations_task():
    """Business Rules 2.5 — دعوت‌های pending که از expires_at گذشته‌اند
    را expired علامت می‌زند."""
    updated = Invitation.unscoped.filter(
        status=Invitation.Status.PENDING,
        expires_at__lt=timezone.now(),
    ).update(status=Invitation.Status.EXPIRED)
    return updated
