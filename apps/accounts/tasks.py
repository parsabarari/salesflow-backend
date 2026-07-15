from celery import shared_task
from django.conf import settings
from django.core.mail import send_mail

from apps.accounts.models import User


@shared_task
def send_verification_email_task(user_id):
    from apps.accounts.services import EmailVerificationService  # جلوگیری از circular import

    try:
        user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        return
    uidb64, token = EmailVerificationService.generate_link_parts(user)
    verify_url = f"{settings.FRONTEND_BASE_URL}/verify-email?uid={uidb64}&token={token}"
    send_mail(
        subject="Verify your email",
        message=f"Click to verify: {verify_url}",
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
    )


@shared_task
def send_password_reset_email_task(user_id, uidb64, token):
    try:
        user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        return
    reset_url = f"{settings.FRONTEND_BASE_URL}/reset-password?uid={uidb64}&token={token}"
    send_mail(
        subject="Reset your password",
        message=f"Click to reset: {reset_url}",
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
    )