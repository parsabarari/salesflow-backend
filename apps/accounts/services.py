import time

from django.conf import settings
from django.contrib.auth.tokens import default_token_generator
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode

from apps.accounts.models import User
from apps.accounts.redis_client import get_redis_client

REFRESH_BLOCKLIST_KEY_PREFIX = "refresh_blocklist:"
USER_TOKENS_KEY_PREFIX = "user_tokens:"


def _decode(value):
    """Redis client ممکن است bytes یا str برگرداند بسته به تنظیم
    decode_responses؛ این تابع هر دو حالت را یکدست می‌کند."""
    return value.decode() if isinstance(value, bytes) else value


class TokenBlocklistService:
    @staticmethod
    def _blocklist_key(jti: str) -> str:
        return f"{REFRESH_BLOCKLIST_KEY_PREFIX}{jti}"

    @staticmethod
    def _user_tokens_key(user_id) -> str:
        return f"{USER_TOKENS_KEY_PREFIX}{user_id}"

    @classmethod
    def blocklist(cls, refresh_token_jti: str, ttl_seconds: int) -> None:
        if ttl_seconds <= 0:
            return
        get_redis_client().setex(cls._blocklist_key(refresh_token_jti), ttl_seconds, "1")

    @classmethod
    def is_blocklisted(cls, jti: str) -> bool:
        return bool(get_redis_client().exists(cls._blocklist_key(jti)))

    @classmethod
    def register_issued_token(cls, user_id, jti: str, expires_at_timestamp: float) -> None:
        """هر بار یک refresh token جدید صادر می‌شود (login) باید صدا
        زده شود؛ بدون این، blocklist_all_for_user هیچ jti ای پیدا
        نمی‌کند و قانون ۲.۳ عملاً کار نمی‌کند."""
        redis = get_redis_client()
        key = cls._user_tokens_key(user_id)
        redis.zadd(key, {jti: expires_at_timestamp})
        refresh_lifetime = int(settings.SIMPLE_JWT["REFRESH_TOKEN_LIFETIME"].total_seconds())
        redis.expire(key, refresh_lifetime + 3600)

    @classmethod
    def blocklist_all_for_user(cls, user_id) -> None:
        redis = get_redis_client()
        key = cls._user_tokens_key(user_id)
        now = time.time()
        still_valid = redis.zrangebyscore(key, now, "+inf", withscores=True)
        for jti, expires_at_timestamp in still_valid:
            ttl_seconds = int(expires_at_timestamp - now)
            cls.blocklist(_decode(jti), ttl_seconds)
        redis.zremrangebyscore(key, "-inf", now)


class EmailVerificationService:
    @staticmethod
    def generate_link_parts(user: User) -> tuple[str, str]:
        from apps.accounts.tokens import email_verification_token_generator  # lazy: جلوگیری از circular import
        uidb64 = urlsafe_base64_encode(force_bytes(user.pk))
        token = email_verification_token_generator.make_token(user)
        return uidb64, token

    @staticmethod
    def verify(uid: str, token: str) -> bool:
        from apps.accounts.tokens import email_verification_token_generator  # lazy
        try:
            user_id = force_str(urlsafe_base64_decode(uid))
            user = User.objects.get(pk=user_id)
        except (User.DoesNotExist, ValueError, TypeError, OverflowError):
            return False
        if not email_verification_token_generator.check_token(user, token):
            return False
        user.is_email_verified = True
        user.save(update_fields=["is_email_verified"])
        return True


class PasswordResetService:
    @staticmethod
    def request(email: str) -> None:
        from apps.accounts.tasks import send_password_reset_email_task

        try:
            user = User.objects.get(email__iexact=email)
        except User.DoesNotExist:
            # عمداً وجود/عدم‌وجود ایمیل را لو نمی‌دهیم (جلوگیری از
            # user enumeration) — همیشه موفق برمی‌گردیم.
            return
        uidb64 = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)
        send_password_reset_email_task.delay(user.id, uidb64, token)

    @staticmethod
    def confirm(uid: str, token: str, new_password: str) -> bool:
        try:
            user_id = force_str(urlsafe_base64_decode(uid))
            user = User.objects.get(pk=user_id)
        except (User.DoesNotExist, ValueError, TypeError, OverflowError):
            return False

        if not default_token_generator.check_token(user, token):
            return False

        user.set_password(new_password)
        user.save(update_fields=["password"])
        TokenBlocklistService.blocklist_all_for_user(user.id)  # Business Rules 2.3
        return True
    