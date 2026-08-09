from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.core.context import clear_current_organization, set_current_organization
from apps.organizations.models import Membership, MembershipRole, Organization


class RequestLoggingMiddlewareTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(email="logtest@example.com", password="secret")

    def test_request_is_logged_with_status_and_duration(self):
        self.client.force_authenticate(user=self.user)
        with self.assertLogs("apps.core.request", level="INFO") as cm:
            self.client.get("/api/v1/auth/me/")

        self.assertEqual(len(cm.records), 1)
        record = cm.records[0]
        self.assertEqual(record.status_code, 200)
        self.assertEqual(record.method, "GET")
        self.assertIsInstance(record.duration_ms, float)

    def test_organization_id_captured_for_org_scoped_endpoint(self):
        organization = Organization.objects.create(name="Acme")
        set_current_organization(organization.id)
        try:
            Membership.objects.create(user=self.user, organization=organization, role=MembershipRole.VIEWER)
        finally:
            clear_current_organization()

        self.client.force_authenticate(user=self.user)
        with self.settings(ROOT_URLCONF="apps.core.tests.urls"):
            with self.assertLogs("apps.core.request", level="INFO") as cm:
                self.client.get(f"/api/v1/organizations/{organization.id}/probe/")

        record = cm.records[0]
        self.assertEqual(record.organization_id, organization.id)

    def test_unresolved_path_does_not_crash_logging(self):
        with self.assertLogs("apps.core.request", level="INFO") as cm:
            self.client.get("/this/path/does/not/exist/")
        record = cm.records[0]
        self.assertEqual(record.status_code, 404)
        self.assertIsNone(record.organization_id)
