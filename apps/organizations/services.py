from django.db import transaction

from apps.accounts.models import User
from apps.accounts.tasks import send_verification_email_task
from apps.core.context import clear_current_organization, set_current_organization
from apps.organizations.models import Membership, MembershipRole, Organization


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
    