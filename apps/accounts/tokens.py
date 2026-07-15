# apps/accounts/tokens.py
from rest_framework_simplejwt.tokens import RefreshToken as SimpleJWTRefreshToken
from django.contrib.auth.tokens import PasswordResetTokenGenerator

from apps.accounts.redis_client import get_redis_client
from apps.accounts.services import TokenBlocklistService


class RefreshToken(SimpleJWTRefreshToken):
    @classmethod
    def for_user(cls, user):
        token = super().for_user(user)
        TokenBlocklistService.register_issued_token(
            user_id=user.id,
            jti=str(token["jti"]),
            expires_at_timestamp=token["exp"],
        )
        return token


class EmailVerificationTokenGenerator(PasswordResetTokenGenerator):
    key_salt = "apps.accounts.tokens.EmailVerificationTokenGenerator"

    def _make_hash_value(self, user, timestamp):
        return f"{user.pk}{user.password}{timestamp}{user.is_email_verified}{user.email}"


email_verification_token_generator = EmailVerificationTokenGenerator()