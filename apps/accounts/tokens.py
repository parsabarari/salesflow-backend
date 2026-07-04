from rest_framework_simplejwt.tokens import RefreshToken as SimpleJWTRefreshToken

from apps.accounts.redis_client import get_redis_client
from apps.accounts.services import USER_TOKENS_KEY_PREFIX


class RefreshToken(SimpleJWTRefreshToken):
    @classmethod
    def for_user(cls, user):
        token = super().for_user(user)
        get_redis_client().sadd(f"{USER_TOKENS_KEY_PREFIX}{user.id}", str(token["jti"]))
        return token
