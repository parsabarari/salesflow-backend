import logging
import time

from apps.core.context import disable_unscoped_mode, enable_unscoped_mode

logger = logging.getLogger("apps.core.request")


class AdminOrgBypassMiddleware:
    """Enables the org-scoping bypass (apps/core/context.py) only for
    requests under /admin/ — the one and only place in the codebase
    that decides this based on a URL path. Every manager and queryset
    checks a plain boolean; none of them know this exists."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        is_admin_request = request.path.startswith("/admin/")
        if is_admin_request:
            enable_unscoped_mode()
        try:
            return self.get_response(request)
        finally:
            if is_admin_request:
                disable_unscoped_mode()


class RequestLoggingMiddleware:
    """docs/06-architecture.md §7 — minimum observability requirement:
    "standard request logging (status code, latency, org_id) on the web
    service." Placed first in MIDDLEWARE (base.py) so its timer wraps
    the entire request/response cycle, including every other middleware.

    organization_id is read from the resolved URL kwargs rather than
    from apps.core.context's contextvar, since OrgScopedViewSetMixin
    already clears that context (finalize_response) before control
    returns up the middleware chain to this point — by the time we'd
    read it here, it would already be gone. Every tenant-scoped URL in
    this codebase carries organization_id in the path itself
    (AGENTS.md: "Keep organization_id in the URL path... not a custom
    header"), so resolver_match.kwargs is a reliable, always-available
    source instead.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        start = time.monotonic()
        response = self.get_response(request)
        duration_ms = round((time.monotonic() - start) * 1000, 2)

        organization_id = None
        resolver_match = getattr(request, "resolver_match", None)
        if resolver_match is not None:
            organization_id = resolver_match.kwargs.get("organization_id")

        logger.info(
            "request",
            extra={
                "method": request.method,
                "path": request.path,
                "status_code": response.status_code,
                "duration_ms": duration_ms,
                "organization_id": organization_id,
            },
        )
        return response
