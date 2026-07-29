from contextvars import ContextVar

_current_organization_id: ContextVar[int | None] = ContextVar(
    "current_organization_id", default=None
)
_unscoped_mode: ContextVar[bool] = ContextVar("unscoped_mode", default=False)


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


def enable_unscoped_mode() -> None:
    """A narrow, deliberate escape hatch — while active, org-scoped
    managers treat themselves as globally unscoped. Nothing in this
    module knows or cares what turns this on; apps/core/middleware.py
    is the only caller, restricted to /admin/ requests. No manager or
    queryset anywhere references HTTP concepts — they only ever check
    this boolean."""
    _unscoped_mode.set(True)


def disable_unscoped_mode() -> None:
    _unscoped_mode.set(False)


def is_unscoped_mode() -> bool:
    return _unscoped_mode.get()


def organization_scope_filter(field_path: str) -> dict:
    """Single shared helper — every org-scoped manager and every
    'child of a parent' queryset (LeadStageHistory, Contact,
    CustomerLeadLink, CommentMention, Notification) calls this instead
    of each hand-rolling its own `if is_unscoped_mode(): ...` branch.
    field_path is the ORM lookup reaching organization_id, e.g.
    "organization_id" directly, or "lead__organization_id" through a
    parent. A brand-new manager written against this helper gets the
    admin bypass automatically, for free, with no risk of forgetting it."""
    if is_unscoped_mode():
        return {}
    return {field_path: get_current_organization()}
