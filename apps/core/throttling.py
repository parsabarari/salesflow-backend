"""Rate limiting classes for the three unauthenticated endpoints named
in docs/06-architecture.md §5. Backed by Django's cache framework,
which points at Redis (config/settings/base.py CACHES) — the same
Redis instance already used for the JWT blocklist/idempotency/dashboard
cache (06-architecture.md §1, §4), so this works correctly across the
horizontally-scaled `web` service (06-architecture.md §6) rather than
a per-process in-memory count.

No authenticated-endpoint throttling is added here — 06-architecture.md
§5 is explicit that only these three endpoints get rate limits in MVP.
"""

from rest_framework.throttling import SimpleRateThrottle


class LoginRateThrottle(SimpleRateThrottle):
    """POST /auth/login/ — 10 attempts / 15 min, keyed on IP + email
    combined (06-architecture.md §5), so an attacker can't dodge the
    limit either by rotating IPs against one email or by spraying many
    emails from one IP without ever repeating a (IP, email) pair."""

    scope = "login"
    rate = "10/15min"

    def parse_rate(self, rate):
        num, period = rate.split("/")
        if period.endswith("min"):
            duration = int(period[:-3]) * 60
        else:
            duration = {"s": 1, "m": 60, "h": 3600, "d": 86400}[period[0]]
        return int(num), duration

    def get_cache_key(self, request, view):
        email = (request.data.get("email") or "").strip().lower()
        ident = f"{self.get_ident(request)}:{email}"
        return self.cache_format % {"scope": self.scope, "ident": ident}


class PasswordResetRequestThrottle(SimpleRateThrottle):
    """POST /auth/password-reset/request/ — 5 / hour per email
    (06-architecture.md §5). Keyed on email, not IP, since the resource
    being protected is "how many reset emails does this address get",
    regardless of who's asking."""

    scope = "password_reset_request"
    rate = "5/h"

    def get_cache_key(self, request, view):
        email = (request.data.get("email") or "").strip().lower()
        if not email:
            # No email in the payload at all — let the serializer's own
            # validation reject the request instead of throttling on an
            # empty key that every malformed request would share.
            return None
        return self.cache_format % {"scope": self.scope, "ident": email}


class InvitationAcceptThrottle(SimpleRateThrottle):
    """POST /auth/invitations/{token}/accept/ — 10 / hour per token
    (06-architecture.md §5). Keyed on the token itself, which is
    already unique and unguessable (secrets.token_urlsafe(32) per
    InvitationService.create), so this limits brute-force attempts
    against a single invitation without affecting other invitations."""

    scope = "invitation_accept"
    rate = "10/h"

    def get_cache_key(self, request, view):
        token = view.kwargs.get("token", "")
        if not token:
            return None
        return self.cache_format % {"scope": self.scope, "ident": token}
