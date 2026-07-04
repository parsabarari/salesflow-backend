from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone

from apps.accounts.models import User
from apps.organizations.models import Membership, Organization


class MembershipModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="member@example.com", password="secret")
        self.manager_user = User.objects.create_user(email="manager@example.com", password="secret")
        self.organization = Organization.objects.create(name="Acme")

    def test_active_membership_unique_per_user_and_organization(self):
        Membership.objects.create(
            user=self.user,
            organization=self.organization,
            role=Membership.Role.VIEWER,
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Membership.objects.create(
                    user=self.user,
                    organization=self.organization,
                    role=Membership.Role.SALES_AGENT,
                )

    def test_soft_deleted_membership_does_not_block_replacement(self):
        membership = Membership.objects.create(
            user=self.user,
            organization=self.organization,
            role=Membership.Role.VIEWER,
        )
        membership.deleted_at = timezone.now()
        membership.save(update_fields=["deleted_at"])

        replacement = Membership.objects.create(
            user=self.user,
            organization=self.organization,
            role=Membership.Role.SALES_AGENT,
        )

        self.assertIsNotNone(replacement.pk)

    def test_reports_to_can_reference_another_membership(self):
        manager = Membership.objects.create(
            user=self.manager_user,
            organization=self.organization,
            role=Membership.Role.SALES_MANAGER,
        )
        agent = Membership.objects.create(
            user=self.user,
            organization=self.organization,
            role=Membership.Role.SALES_AGENT,
            reports_to=manager,
        )

        self.assertEqual(agent.reports_to, manager)

    def test_reports_to_is_nullable(self):
        membership = Membership.objects.create(
            user=self.user,
            organization=self.organization,
            role=Membership.Role.VIEWER,
        )

        self.assertIsNone(membership.reports_to)
