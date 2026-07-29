from apps.core.context import disable_unscoped_mode, enable_unscoped_mode


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
