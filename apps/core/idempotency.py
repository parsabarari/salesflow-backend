import json

from apps.core.redis_client import get_redis_client

IDEMPOTENCY_KEY_PREFIX = "idempotency:"
# Not specified in the docs — a reasonable default, easy to change.
IDEMPOTENCY_TTL_SECONDS = 60 * 60 * 24


class IdempotencyService:
    """API Spec §1.6 — repeated POST with the same Idempotency-Key header
    returns the original response without re-executing the side effect.
    Scoped per (organization_id, path, key) so the same key value can't
    collide across different orgs or endpoints.

    Known limitation, acceptable at this scale (5-50 users/org, PRD §3):
    not race-safe under two truly concurrent identical requests — no
    locking, just a cache check-then-store. Flagging rather than
    building distributed locking that isn't justified yet."""

    @staticmethod
    def _cache_key(*, organization_id, path, idempotency_key) -> str:
        return f"{IDEMPOTENCY_KEY_PREFIX}{organization_id}:{path}:{idempotency_key}"

    @staticmethod
    def get_cached_response(*, organization_id, path, idempotency_key):
        if not idempotency_key:
            return None
        raw = get_redis_client().get(
            IdempotencyService._cache_key(organization_id=organization_id, path=path, idempotency_key=idempotency_key)
        )
        return json.loads(raw) if raw is not None else None

    @staticmethod
    def store_response(*, organization_id, path, idempotency_key, status_code, data) -> None:
        if not idempotency_key:
            return
        get_redis_client().setex(
            IdempotencyService._cache_key(organization_id=organization_id, path=path, idempotency_key=idempotency_key),
            IDEMPOTENCY_TTL_SECONDS,
            json.dumps({"status_code": status_code, "data": data}),
        )
