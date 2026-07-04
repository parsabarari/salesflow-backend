from django.conf import settings

from apps.accounts.redis_client import get_redis_client

REFRESH_BLOCKLIST_KEY_PREFIX = "refresh_blocklist:"
USER_TOKENS_KEY_PREFIX = "user_tokens:"


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
    def blocklist_all_for_user(cls, user_id) -> None:
        redis = get_redis_client()
        jtis = redis.smembers(cls._user_tokens_key(user_id))
        ttl_seconds = int(settings.SIMPLE_JWT["REFRESH_TOKEN_LIFETIME"].total_seconds())
        for jti in jtis:
            cls.blocklist(jti, ttl_seconds)
