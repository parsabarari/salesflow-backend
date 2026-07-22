from django.db import models
from django.db.models import Q

from apps.core.context import get_current_organization
from apps.core.managers import BaseQuerySet, OrgScopedAllManager, OrgScopedManager, UnscopedManager
from apps.core.models import CIEmailField, OrgScopedModel, SoftDeleteModel, TimeStampedModel


class CustomerType(models.TextChoices):
    COMPANY = "company", "Company"
    INDIVIDUAL = "individual", "Individual"


class Customer(TimeStampedModel, SoftDeleteModel, OrgScopedModel):
    Type = CustomerType

    type = models.CharField(max_length=20, choices=Type.choices)
    name = models.CharField(max_length=255)
    email = CIEmailField(null=True, blank=True)
    phone = models.CharField(max_length=30, null=True, blank=True)
    # Business Rules 6.1: for type=company, at least one Contact must
    # exist — enforced at the service layer (Phase 2.1 service, next
    # step), not a DB constraint, per ERD §9 note.

    objects = OrgScopedManager()
    all_objects = OrgScopedAllManager()
    unscoped = UnscopedManager()

    class Meta:
        db_table = "customers"
        constraints = [
            models.CheckConstraint(condition=Q(type__in=CustomerType.values), name="customers_type_valid"),
        ]
        indexes = [
            models.Index(fields=["organization", "email"], name="idx_customers_org_email"),
            models.Index(fields=["organization", "phone"], name="idx_customers_org_phone"),
        ]

    def __str__(self):
        return self.name


class ContactQuerySet(BaseQuerySet):
    def for_current_organization(self):
        return self.filter(customer__organization_id=get_current_organization())


class ContactManager(models.Manager.from_queryset(ContactQuerySet)):
    """Contact has no organization_id of its own (ERD §10) — reachable
    via customer_id -> customer.organization_id, same pattern as
    LeadStageHistory. Excludes soft-deleted rows."""

    def get_queryset(self):
        return super().get_queryset().for_current_organization().active()


class ContactAllManager(models.Manager.from_queryset(ContactQuerySet)):
    """Org-scoped via customer, includes soft-deleted rows."""

    def get_queryset(self):
        return super().get_queryset().for_current_organization()


class Contact(TimeStampedModel, SoftDeleteModel):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name="contacts")
    name = models.CharField(max_length=255)
    email = CIEmailField(null=True, blank=True)
    phone = models.CharField(max_length=30, null=True, blank=True)

    objects = ContactManager()
    all_objects = ContactAllManager()
    unscoped = models.Manager()

    class Meta:
        db_table = "contacts"
        # customer_id is auto-indexed by Django's default FK behavior —
        # no explicit index needed for it, only for the non-FK columns.
        indexes = [
            models.Index(fields=["email"], name="idx_contacts_email"),
            models.Index(fields=["phone"], name="idx_contacts_phone"),
        ]

    def __str__(self):
        return self.name


class CustomerLeadLinkQuerySet(BaseQuerySet):
    def for_current_organization(self):
        return self.filter(customer__organization_id=get_current_organization())


class CustomerLeadLinkManager(models.Manager.from_queryset(CustomerLeadLinkQuerySet)):
    def get_queryset(self):
        return super().get_queryset().for_current_organization()


class CustomerLeadLink(models.Model):
    """No organization_id/deleted_at of its own (ERD §11) — a pure
    history join. OneToOneField on `lead` gives the UNIQUE(lead_id)
    constraint ERD §11 asks for automatically."""

    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name="lead_links")
    lead = models.OneToOneField("leads.Lead", on_delete=models.PROTECT, related_name="customer_link")
    linked_at = models.DateTimeField(auto_now_add=True)

    objects = CustomerLeadLinkManager()
    unscoped = models.Manager()

    class Meta:
        db_table = "customer_lead_links"
        # customer_id and lead_id are both auto-indexed by Django's
        # default FK/OneToOne behavior — no explicit indexes needed.

    def __str__(self):
        return f"Customer #{self.customer_id} <- Lead #{self.lead_id}"
