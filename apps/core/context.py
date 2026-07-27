from contextvars import ContextVar

_current_organization_id: ContextVar[int | None] = ContextVar(
    "current_organization_id", default=None
)
_admin_bypass: ContextVar[bool] = ContextVar("admin_bypass", default=False)


def set_current_organization(organization_id: int) -> None:
    _current_organization_id.set(organization_id)


def get_current_organization() -> int:
    organization_id = _current_organization_id.get()
    if organization_id is None:
        raise RuntimeError("Organization context is not set.")
    return organization_id


def get_current_organization_or_none():
    return _current_organization_id.get(None)


def clear_current_organization() -> None:
    _current_organization_id.set(None)


def enable_admin_bypass() -> None:
    """Django's admin internals call a model's plain default manager
    directly from several different internal code paths (formset pk
    field construction, empty_form media generation, and others) that
    can never be reached by overriding any ModelAdmin/InlineModelAdmin
    method — they run before, or entirely outside, any admin hook.
    Rather than patching each new Django-internal call site as it
    surfaces, every org-scoped manager checks this flag and behaves as
    globally unscoped for the duration of an admin request. Admin is
    superuser-only, so this is a deliberate, contained exception to the
    normal fail-closed behavior everywhere else in the app."""
    _admin_bypass.set(True)


def disable_admin_bypass() -> None:
    _admin_bypass.set(False)


def is_admin_bypass() -> bool:
    return _admin_bypass.get()