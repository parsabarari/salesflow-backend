from django.db import models
from django.utils import timezone

from apps.core.context import get_current_organization, get_current_organization_or_none



class BaseQuerySet(models.QuerySet):
    def active(self):
        return self.filter(deleted_at__isnull=True)

    def deleted(self):
        return self.filter(deleted_at__isnull=False)

    def for_organization(self, organization_id):
        return self.filter(organization_id=organization_id)


# --- Soft-delete only (global models: Organization, User) ---
class ActiveManager(models.Manager.from_queryset(BaseQuerySet)):
    def get_queryset(self):
        return super().get_queryset().active()


class AllManager(models.Manager.from_queryset(BaseQuerySet)):
    """Sees everything, including soft-deleted. No org filter — used only
    on global models."""
    pass

class OrgScopedCreateMixin:
    """create() doesn't need the read-time org filter — organization is
    explicit via the `organization=` kwarg, not ambient context. This
    bypasses get_queryset() entirely for creation, but still guards
    against a mismatch if context IS set and disagrees with the
    explicit organization (catches real bugs without requiring context
    to exist just to create a fixture/object)."""

    def create(self, **kwargs):
        obj = self.model(**kwargs)
        current_org_id = get_current_organization_or_none()
        if (
            current_org_id is not None
            and getattr(obj, "organization_id", None) is not None
            and obj.organization_id != current_org_id
        ):
            raise RuntimeError(
                f"{self.model.__name__}.objects.create() organization "
                f"({obj.organization_id}) does not match current context "
                f"({current_org_id})."
            )
        obj.save(using=self._db)
        return obj

class OrgScopedManager(OrgScopedCreateMixin, models.Manager.from_queryset(BaseQuerySet)):
    def get_queryset(self):
        return super().get_queryset().filter(
            organization_id=get_current_organization()
        )


class OrgScopedAllManager(OrgScopedCreateMixin, models.Manager.from_queryset(BaseQuerySet)):
    """Org-filtered but includes soft-deleted rows — for restore/audit views."""
    def get_queryset(self):
        return super().get_queryset().filter(
            organization_id=get_current_organization()
        )


# --- Org-scoped WITHOUT soft-delete (Invitation — no deleted_at per ERD §4) ---
class OrgScopedNoSoftDeleteManager(OrgScopedCreateMixin, models.Manager.from_queryset(BaseQuerySet)):
    def get_queryset(self):
        return super().get_queryset().filter(
            organization_id=get_current_organization()
        )


class UnscopedManager(models.Manager.from_queryset(BaseQuerySet)):
    """No automatic organization filter, no soft-delete filter applied
    in get_queryset(). Used ONLY where organization_id itself is the
    thing being verified (e.g. the membership bootstrap check in
    OrgScopedViewSetMixin.initial(), which runs BEFORE the org context
    is set — an org-scoped manager can't be used to decide whether to
    grant access to that same org). Never use this for normal reads."""
    pass
