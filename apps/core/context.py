from contextvars import ContextVar

_current_organization_id: ContextVar[int | None] = ContextVar(
    "current_organization_id", default=None
)


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
