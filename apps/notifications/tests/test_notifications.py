from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.core.context import clear_current_organization, set_current_organization
from apps.leads.services import LeadService
from apps.notifications.models import Notification, NotificationType
from apps.organizations.models import Membership, MembershipRole, Organization


class NotificationEndpointTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.organization = Organization.objects.create(name="Acme")

        set_current_organization(self.organization.id)
        self.owner = Membership.objects.create(
            user=User.objects.create_user(email="owner@example.com", password="secret"),
            organization=self.organization,
            role=MembershipRole.OWNER,
        )
        self.other = Membership.objects.create(
            user=User.objects.create_user(email="other@example.com", password="secret"),
            organization=self.organization,
            role=MembershipRole.SALES_AGENT,
        )
        # LeadService.create_lead already fires a LEAD_ASSIGNED
        # notification to its owner (wired last chunk) — reused here
        # instead of creating Notification rows by hand.
        LeadService.create_lead(organization=self.organization, owner=self.owner, source="web", email="a@example.com")
        LeadService.create_lead(organization=self.organization, owner=self.owner, source="web", email="b@example.com")
        LeadService.create_lead(organization=self.organization, owner=self.other, source="web", email="c@example.com")
        clear_current_organization()

    def _list_url(self):
        return f"/api/v1/organizations/{self.organization.id}/notifications/"

    def _read_url(self, notification_id):
        return f"/api/v1/organizations/{self.organization.id}/notifications/{notification_id}/read/"

    def _read_all_url(self):
        return f"/api/v1/organizations/{self.organization.id}/notifications/read-all/"

    def test_sees_only_own_notifications(self):
        self.client.force_authenticate(user=self.owner.user)
        response = self.client.get(self._list_url())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 2)  # only the owner's two leads, not other's

    def test_filter_by_is_read(self):
        self.client.force_authenticate(user=self.owner.user)
        all_response = self.client.get(self._list_url())
        first_id = all_response.data[0]["id"]
        self.client.post(self._read_url(first_id))

        unread_response = self.client.get(self._list_url() + "?is_read=false")
        self.assertEqual(len(unread_response.data), 1)

        read_response = self.client.get(self._list_url() + "?is_read=true")
        self.assertEqual(len(read_response.data), 1)

    def test_mark_read(self):
        self.client.force_authenticate(user=self.owner.user)
        list_response = self.client.get(self._list_url())
        notification_id = list_response.data[0]["id"]

        response = self.client.post(self._read_url(notification_id))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["is_read"])

    def test_cannot_mark_another_users_notification_read(self):
        self.client.force_authenticate(user=self.owner.user)
        list_response = self.client.get(self._list_url())
        owner_notification_id = list_response.data[0]["id"]

        self.client.force_authenticate(user=self.other.user)
        response = self.client.post(self._read_url(owner_notification_id))
        self.assertEqual(response.status_code, 404)

    def test_mark_all_read(self):
        self.client.force_authenticate(user=self.owner.user)
        response = self.client.post(self._read_all_url())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["updated_count"], 2)

        set_current_organization(self.organization.id)
        try:
            unread_count = Notification.objects.filter(recipient_membership=self.owner, is_read=False).count()
        finally:
            clear_current_organization()
        self.assertEqual(unread_count, 0)
