from apps.core.context import disable_admin_bypass, enable_admin_bypass


class AdminOrgBypassMiddleware:
    """Enables the admin org-context bypass (apps/core/context.py) for
    the duration of any request under /admin/ only — every other
    endpoint in the app keeps its original fail-closed org-scoping
    behavior completely untouched."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        is_admin_request = request.path.startswith("/admin/")
        if is_admin_request:
            enable_admin_bypass()
        try:
            return self.get_response(request)
        finally:
            if is_admin_request:
                disable_admin_bypass()
