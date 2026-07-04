from django.db import models
from django.db.models.functions import Now
from django.utils import timezone


class CIEmailField(models.EmailField):
    description = "Case-insensitive email stored as PostgreSQL citext"

    def db_type(self, connection):
        if connection.vendor == "postgresql":
            return "citext"
        return super().db_type(connection)


class OrganizationScopedQuerySet(models.QuerySet):
    def for_organization(self, organization_id):
        return self.filter(organization_id=organization_id)


class OrganizationScopedManager(models.Manager.from_queryset(OrganizationScopedQuerySet)):
    pass


class SoftDeleteQuerySet(OrganizationScopedQuerySet):
    def active(self):
        return self.filter(deleted_at__isnull=True)

    def deleted(self):
        return self.filter(deleted_at__isnull=False)

    def delete(self):
        return self.update(deleted_at=timezone.now())

    def hard_delete(self):
        return super().delete()

    def restore(self):
        return self.update(deleted_at=None)


class SoftDeleteManager(models.Manager.from_queryset(SoftDeleteQuerySet)):
    def get_queryset(self):
        return super().get_queryset().active()

    def include_deleted(self):
        return self.model.all_objects.using(self._db).all()


class SoftDeleteAllManager(models.Manager.from_queryset(SoftDeleteQuerySet)):
    pass


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(db_default=Now(), editable=False)

    class Meta:
        abstract = True


class SoftDeleteModel(models.Model):
    deleted_at = models.DateTimeField(null=True, blank=True)

    objects = SoftDeleteManager()
    all_objects = SoftDeleteAllManager()

    class Meta:
        abstract = True

    def delete(self, using=None, keep_parents=False):
        self.deleted_at = timezone.now()
        self.save(update_fields=["deleted_at"])

    def hard_delete(self, using=None, keep_parents=False):
        return super().delete(using=using, keep_parents=keep_parents)

    def restore(self):
        self.deleted_at = None
        self.save(update_fields=["deleted_at"])


class OrgScopedModel(models.Model):
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="%(app_label)s_%(class)s_set",
    )

    objects = OrganizationScopedManager()

    class Meta:
        abstract = True
