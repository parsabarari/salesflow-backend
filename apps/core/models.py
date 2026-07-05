from django.db import models
from django.db.models.functions import Now
from django.utils import timezone

from apps.core.managers import (OrgScopedManager, ActiveManager,
                                AllManager,)


class CIEmailField(models.EmailField):
    description = "Case-insensitive email stored as PostgreSQL citext"

    def db_type(self, connection):
        if connection.vendor == "postgresql":
            return "citext"
        return super().db_type(connection)


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(db_default=Now(), editable=False)

    class Meta:
        abstract = True


class SoftDeleteModel(models.Model):
    deleted_at = models.DateTimeField(null=True, blank=True)

    objects = ActiveManager()
    all_objects = AllManager()

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


    class Meta:
        abstract = True
