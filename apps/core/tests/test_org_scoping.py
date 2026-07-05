from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.core.context import clear_current_organization, set_current_organization
from apps.organizations.models import Membership, Organization


@override_settings(ROOT_URLCONF="apps.core.tests.urls")
class OrgScopedViewSetMixinTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(email="member@example.com", password="secret")
        self.organization = Organization.objects.create(name="Acme")
        Membership.objects.create(
            user=self.user,
            organization=self.organization,
            role=Membership.Role.VIEWER,
        )
        self.other_organization = Organization.objects.create(name="Other")
        self.client.force_authenticate(user=self.user)

    def test_user_without_membership_gets_404(self):
        response = self.client.get(
            f"/api/v1/organizations/{self.other_organization.id}/probe/"
        )
        self.assertEqual(response.status_code, 404)


class OrgScopedManagerTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="member@example.com", password="secret")
        self.organization_a = Organization.objects.create(name="Org A")
        self.organization_b = Organization.objects.create(name="Org B")
        self.membership_a = Membership.objects.create(
            user=self.user,
            organization=self.organization_a,
            role=Membership.Role.VIEWER,
        )
        self.membership_b = Membership.objects.create(
            user=self.user,
            organization=self.organization_b,
            role=Membership.Role.VIEWER,
        )
        clear_current_organization()

    def test_cross_org_row_never_returned(self):
        set_current_organization(self.organization_a.id)
        try:
            membership_ids = list(Membership.objects.values_list("id", flat=True))
        finally:
            clear_current_organization()

        self.assertEqual(membership_ids, [self.membership_a.id])

    def test_unset_context_raises_runtime_error(self):
        with self.assertRaises(RuntimeError):
            list(Membership.objects.all())


    def test_create_with_mismatched_organization_context_raises(self):
        """اگر context روی سازمان A باشد ولی organization صریحاً B پاس
        داده شود، create باید RuntimeError بدهد — safety net مربوط به
        OrgScopedCreateMixin."""
        set_current_organization(self.organization_a.id)
        try:
            with self.assertRaises(RuntimeError):
                Membership.objects.create(
                    user=self.user,
                    organization=self.organization_b,
                    role=Membership.Role.VIEWER,
                )
        finally:
            clear_current_organization()


    def test_create_without_context_succeeds(self):
        """create() نباید نیاز به context از پیش تنظیم‌شده داشته باشد —
        همان چیزی که خودِ setUp این کلاس هم به آن متکی است (membership_a
        و membership_b بدون set_current_organization ساخته می‌شوند)."""
        organization_c = Organization.objects.create(name="Org C")
        membership = Membership.objects.create(
            user=self.user,
            organization=organization_c,
            role=Membership.Role.VIEWER,
        )
        self.assertIsNotNone(membership.pk)
