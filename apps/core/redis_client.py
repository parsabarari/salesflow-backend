import redis
from django.conf import settings

_client = None


def get_redis_client():
    global _client
    if _client is None:
        _client = redis.from_url(settings.REDIS_URL, decode_responses=True)
    return _client
