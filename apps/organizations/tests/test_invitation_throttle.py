from django.core.cache import cache
from django.test import TestCase
from rest_framework.test import APIClient


class InvitationAcceptThrottleTests(TestCase):
    """06-architecture.md §5 — 10 / hour per token. Uses fabricated
    tokens (no real Invitation needed) since the throttle keys purely
    off the URL token, independent of whether it resolves to a real,
    still-pending invitation."""

    def setUp(self):
        cache.clear()
        self.client = APIClient()

    def tearDown(self):
        cache.clear()

    def _accept(self, token="fake-token-a"):
        return self.client.post(
            f"/api/v1/auth/invitations/{token}/accept/", {"password": "somepassword123"}, format="json"
        )

    def test_11th_attempt_on_same_token_is_throttled(self):
        for _ in range(10):
            response = self._accept()
            self.assertNotEqual(response.status_code, 429)
        response = self._accept()
        self.assertEqual(response.status_code, 429)

    def test_different_token_is_not_affected(self):
        for _ in range(10):
            self._accept(token="fake-token-a")
        response = self._accept(token="fake-token-b")
        self.assertNotEqual(response.status_code, 429)
