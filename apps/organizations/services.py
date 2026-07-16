import secrets
from datetime import timedelta

from django.db import transaction, IntegrityError
from django.utils import timezone

from apps.accounts.models import User
from apps.accounts.tasks import send_verification_email_task
from apps.core.context import clear_current_organization, set_current_organization
from apps.organizations.models import Membership, MembershipRole, Organization, Invitation


INVITATION_EXPIRY_DAYS = 7  # Business Rules 2.5


class SignupService:
    @staticmethod
    @transaction.atomic
    def signup(email: str, password: str, organization_name: str):
        user = User.objects.create_user(email=email, password=password)
        organization = Organization.objects.create(name=organization_name)

        # سازمان تازه ساخته شده، هنوز هیچ request-context ای برایش
        # وجود ندارد؛ باید صریحاً همین‌جا ست شود تا Membership.objects
        # (که org-scoped است) بتواند رکورد را بسازد/بخواند.
        set_current_organization(organization.id)
        try:
            membership = Membership.objects.create(
                user=user,
                organization=organization,
                role=MembershipRole.OWNER,
            )
        finally:
            clear_current_organization()

        send_verification_email_task.delay(user.id)
        return user, organization, membership
    

class InvitationService:
    @staticmethod
    def create(organization, invited_by_membership, email: str, role: str) -> Invitation:
        try:
            with transaction.atomic():
                return Invitation.objects.create(
                    organization=organization,
                    email=email,
                    role=role,
                    invited_by=invited_by_membership,
                    token=secrets.token_urlsafe(32),
                    expires_at=timezone.now() + timedelta(days=INVITATION_EXPIRY_DAYS),
                )
        except IntegrityError:
            raise ValueError(
                "This email already has a pending invitation in this organization. "
                "Use the resend endpoint instead of creating a new one."
            )

    @staticmethod
    def resend(invitation: Invitation) -> Invitation:
        from apps.organizations.tasks import send_invitation_email_task

        invitation.token = secrets.token_urlsafe(32)
        invitation.expires_at = timezone.now() + timedelta(days=INVITATION_EXPIRY_DAYS)
        invitation.save(update_fields=["token", "expires_at"])
        send_invitation_email_task.delay(invitation.id)
        return invitation

    @staticmethod
    @transaction.atomic
    def accept(token: str, password: str) -> Membership:
        try:
            invitation = Invitation.unscoped.get(token=token, status=Invitation.Status.PENDING)
        except Invitation.DoesNotExist:
            raise ValueError("Invalid or already-used invitation token.")

        if invitation.expires_at < timezone.now():
            invitation.status = Invitation.Status.EXPIRED
            invitation.save(update_fields=["status"])
            raise ValueError("This invitation has expired.")

        try:
            user = User.objects.get(email__iexact=invitation.email)
            if not user.check_password(password):
                raise ValueError("Incorrect password for existing account.")
        except User.DoesNotExist:
            user = User.objects.create_user(email=invitation.email, password=password)
            # طبق Business Rules 2.4: کاربر invite-شده با پذیرش لینک
            # (که به ایمیلش ارسال شده) خودکار verified محسوب می‌شود.
            user.is_email_verified = True
            user.save(update_fields=["is_email_verified"])

        set_current_organization(invitation.organization_id)
        try:
            membership, created = Membership.objects.get_or_create(
                user=user,
                organization=invitation.organization,
                defaults={"role": invitation.role},
            )
        finally:
            clear_current_organization()

        invitation.status = Invitation.Status.ACCEPTED
        invitation.save(update_fields=["status"])
        return membership
    