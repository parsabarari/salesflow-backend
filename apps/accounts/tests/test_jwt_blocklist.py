import time

from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.accounts.redis_client import get_redis_client
from apps.accounts.services import (
    REFRESH_BLOCKLIST_KEY_PREFIX,
    USER_TOKENS_KEY_PREFIX,
    TokenBlocklistService,
)
from apps.accounts.tokens import RefreshToken


class JWTBlocklistTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(email="test@example.com", password="secret")
        self.redis = get_redis_client()
        for key in self.redis.scan_iter(f"{REFRESH_BLOCKLIST_KEY_PREFIX}*"):
            self.redis.delete(key)
        for key in self.redis.scan_iter(f"{USER_TOKENS_KEY_PREFIX}*"):
            self.redis.delete(key)

    def test_blocklisted_refresh_token_fails_validation(self):
        refresh = RefreshToken.for_user(self.user)
        refresh_str = str(refresh)
        jti = str(refresh["jti"])
        ttl_seconds = max(int(refresh["exp"] - time.time()), 1)
        TokenBlocklistService.blocklist(jti, ttl_seconds)

        response = self.client.post("/api/v1/auth/refresh/", {"refresh": refresh_str})

        self.assertEqual(response.status_code, 401)

    def test_non_blocklisted_refresh_token_works(self):
        refresh = RefreshToken.for_user(self.user)

        response = self.client.post("/api/v1/auth/refresh/", {"refresh": str(refresh)})

        self.assertEqual(response.status_code, 200)
        self.assertIn("access", response.data)

    def test_blocklist_all_for_user_blocklists_token_issued_before_call(self):
        refresh = RefreshToken.for_user(self.user)
        refresh_str = str(refresh)

        TokenBlocklistService.blocklist_all_for_user(self.user.id)

        response = self.client.post("/api/v1/auth/refresh/", {"refresh": refresh_str})

        self.assertEqual(response.status_code, 401)
