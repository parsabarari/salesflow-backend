from django.core.cache import cache
from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.models import User


class LoginThrottleTests(TestCase):
    """06-architecture.md §5 — 10 attempts / 15 min, IP+email combined."""

    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.user = User.objects.create_user(email="throttle@example.com", password="secret12345")

    def tearDown(self):
        cache.clear()

    def _attempt(self, email="throttle@example.com", password="wrong-password"):
        return self.client.post("/api/v1/auth/login/", {"email": email, "password": password}, format="json")

    def test_11th_attempt_within_window_is_throttled(self):
        for _ in range(10):
            response = self._attempt()
            self.assertNotEqual(response.status_code, 429)
        response = self._attempt()
        self.assertEqual(response.status_code, 429)

    def test_different_email_is_not_affected_by_another_emails_attempts(self):
        for _ in range(10):
            self._attempt(email="throttle@example.com")
        response = self._attempt(email="someone-else@example.com")
        self.assertNotEqual(response.status_code, 429)

    def test_successful_login_still_counts_toward_the_limit(self):
        for _ in range(10):
            response = self._attempt(password="secret12345")  # correct password
            self.assertNotEqual(response.status_code, 429)
        response = self._attempt(password="secret12345")
        self.assertEqual(response.status_code, 429)


class PasswordResetRequestThrottleTests(TestCase):
    """06-architecture.md §5 — 5 / hour per email."""

    def setUp(self):
        cache.clear()
        self.client = APIClient()

    def tearDown(self):
        cache.clear()

    def _request(self, email="throttle@example.com"):
        return self.client.post("/api/v1/auth/password-reset/request/", {"email": email}, format="json")

    def test_6th_request_within_hour_is_throttled(self):
        for _ in range(5):
            response = self._request()
            self.assertNotEqual(response.status_code, 429)
        response = self._request()
        self.assertEqual(response.status_code, 429)

    def test_different_email_is_not_affected(self):
        for _ in range(5):
            self._request(email="a@example.com")
        response = self._request(email="b@example.com")
        self.assertNotEqual(response.status_code, 429)
