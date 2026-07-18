import secrets
from datetime import timedelta

from django.db import transaction, IntegrityError
from django.utils import timezone

from apps.accounts.models import User
from apps.accounts.tasks import send_verification_email_task
from apps.core.context import clear_current_organization, set_current_organization
from apps.organizations.models import Membership, MembershipRole, Organization, Invitation
from apps.audit.models import AuditActionType
from apps.audit.services import AuditLogService


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
    

class TeamService:
    """Business Rules 3.2 — flat, one-level 'team' resolution via
    Membership.reports_to. Deliberately does not recurse into
    sub-reports; a Sales Manager's team is exactly the Memberships
    that report directly to them, nothing deeper."""

    @staticmethod
    def team_membership_ids(manager_membership: Membership) -> list[int]:
        return list(
            Membership.objects.filter(
                reports_to=manager_membership,
                deleted_at__isnull=True,
            ).values_list("id", flat=True)
        )

    @staticmethod
    def is_in_team(manager_membership: Membership, target_membership_id: int) -> bool:
        return Membership.objects.filter(
            id=target_membership_id,
            reports_to=manager_membership,
            deleted_at__isnull=True,
        ).exists()


class MembershipService:
    @staticmethod
    @transaction.atomic
    def change_role(*, actor_membership: Membership, target_membership: Membership, new_role: str) -> Membership:
        # Business Rules 3.4: a user can never elevate their own role.
        # Conservative reading (no role-hierarchy is defined in the docs
        # to distinguish "elevate" from "demote"): self-role-change is
        # disallowed outright via this endpoint.
        if actor_membership.id == target_membership.id:
            raise ValueError("You cannot change your own role.")

        # PRD 5.3: ownership transfer is explicitly excluded from Admin's
        # permissions — only the current Owner can promote someone to Owner.
        if new_role == MembershipRole.OWNER and actor_membership.role != MembershipRole.OWNER:
            raise ValueError("Only the Owner can transfer ownership.")

        old_role = target_membership.role
        target_membership.role = new_role
        target_membership.save(update_fields=["role"])

        action_type = (
            AuditActionType.OWNERSHIP_TRANSFERRED
            if new_role == MembershipRole.OWNER
            else AuditActionType.ROLE_CHANGED
        )
        AuditLogService.record(
            organization=target_membership.organization,
            actor_membership=actor_membership,
            action_type=action_type,
            target=target_membership,
            metadata={"old_role": old_role, "new_role": new_role},
        )
        return target_membership

    @staticmethod
    @transaction.atomic
    def change_reports_to(*, actor_membership: Membership, target_membership: Membership, reports_to_membership) -> Membership:
        if reports_to_membership is not None:
            if reports_to_membership.organization_id != target_membership.organization_id:
                raise ValueError("reports_to must reference a Membership in the same organization.")
            if reports_to_membership.id == target_membership.id:
                raise ValueError("A Membership cannot report to itself.")

        target_membership.reports_to = reports_to_membership
        target_membership.save(update_fields=["reports_to"])
        # NOTE: Business Rules 3.3 only names role changes as generating
        # an audit event — reports_to changes aren't in the closed
        # action_type list (Business Rules 11.1), so deliberately not
        # logged here. Flagging in case that's an oversight in the docs
        # rather than an intentional omission.
        return target_membership

    @staticmethod
    @transaction.atomic
    def remove(*, actor_membership: Membership, target_membership: Membership) -> Membership:
        if actor_membership.id == target_membership.id:
            raise ValueError("You cannot remove your own membership.")

        old_role = target_membership.role
        target_membership.delete()  # soft delete, SoftDeleteModel.delete()
        AuditLogService.record(
            organization=target_membership.organization,
            actor_membership=actor_membership,
            action_type=AuditActionType.MEMBER_REMOVED,
            target=target_membership,
            metadata={"removed_role": old_role},
        )
        return target_membership
    