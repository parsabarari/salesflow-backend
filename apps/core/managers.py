from django.db import models
from django.utils import timezone

from apps.core.context import get_current_organization, get_current_organization_or_none, is_admin_bypass


class BaseQuerySet(models.QuerySet):
    def active(self):
        return self.filter(deleted_at__isnull=True)

    def deleted(self):
        return self.filter(deleted_at__isnull=False)

    def for_organization(self, organization_id):
        return self.filter(organization_id=organization_id)


class ActiveManager(models.Manager.from_queryset(BaseQuerySet)):
    def get_queryset(self):
        return super().get_queryset().active()


class AllManager(models.Manager.from_queryset(BaseQuerySet)):
    pass


class OrgScopedCreateMixin:
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
        queryset = super().get_queryset().filter(deleted_at__isnull=True)
        if is_admin_bypass():
            return queryset
        return queryset.filter(organization_id=get_current_organization())


class OrgScopedAllManager(OrgScopedCreateMixin, models.Manager.from_queryset(BaseQuerySet)):
    def get_queryset(self):
        queryset = super().get_queryset()
        if is_admin_bypass():
            return queryset
        return queryset.filter(organization_id=get_current_organization())


class OrgScopedNoSoftDeleteManager(OrgScopedCreateMixin, models.Manager.from_queryset(BaseQuerySet)):
    def get_queryset(self):
        queryset = super().get_queryset()
        if is_admin_bypass():
            return queryset
        return queryset.filter(organization_id=get_current_organization())


class UnscopedManager(models.Manager.from_queryset(BaseQuerySet)):
    pass
