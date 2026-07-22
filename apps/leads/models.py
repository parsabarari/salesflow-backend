from django.db import models
from django.db.models import Q
from django.db.models.functions import Now

from apps.core.context import get_current_organization
from apps.core.managers import (
    BaseQuerySet,
    OrgScopedAllManager,
    OrgScopedManager,
    OrgScopedNoSoftDeleteManager,
    UnscopedManager,
)
from apps.core.models import CIEmailField, OrgScopedModel, SoftDeleteModel, TimeStampedModel


class LeadStage(models.TextChoices):
    NEW = "new", "New"
    CONTACTED = "contacted", "Contacted"
    QUALIFIED = "qualified", "Qualified"
    PROPOSAL = "proposal", "Proposal"
    NEGOTIATION = "negotiation", "Negotiation"
    WON = "won", "Won"
    LOST = "lost", "Lost"


class Tag(TimeStampedModel, SoftDeleteModel, OrgScopedModel):
    name = models.CharField(max_length=50)

    objects = OrgScopedManager()
    all_objects = OrgScopedAllManager()
    unscoped = UnscopedManager()

    class Meta:
        db_table = "tags"
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "name"],
                condition=Q(deleted_at__isnull=True),
                name="uniq_active_tag_organization_name",
            ),
        ]

    def __str__(self):
        return self.name


class Lead(TimeStampedModel, SoftDeleteModel, OrgScopedModel):
    Stage = LeadStage

    owner = models.ForeignKey(
        "organizations.Membership",
        on_delete=models.PROTECT,
        related_name="owned_leads",
    )
    source = models.CharField(max_length=100)
    email = CIEmailField(null=True, blank=True)
    phone = models.CharField(max_length=30, null=True, blank=True)
    stage = models.CharField(max_length=20, choices=Stage.choices, default=Stage.NEW)
    lost_reason = models.TextField(null=True, blank=True)
    is_archived = models.BooleanField(default=False)
    requires_manual_customer_selection = models.BooleanField(default=False)
    customer = models.ForeignKey(
        "customers.Customer",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="won_leads",
    )

    tags = models.ManyToManyField(Tag, through="LeadTag", related_name="leads")

    objects = OrgScopedManager()
    all_objects = OrgScopedAllManager()
    unscoped = UnscopedManager()

    class Meta:
        db_table = "leads"
        constraints = [
            models.CheckConstraint(
                condition=Q(email__isnull=False) | Q(phone__isnull=False),
                name="leads_email_or_phone_required",
            ),
            models.CheckConstraint(
                condition=~Q(stage="lost") | Q(lost_reason__isnull=False),
                name="leads_lost_requires_reason",
            ),
            models.CheckConstraint(
                condition=Q(stage__in=LeadStage.values),
                name="leads_stage_valid",
            ),
        ]
        indexes = [
            models.Index(fields=["organization", "owner"], name="idx_leads_org_owner"),
            models.Index(fields=["organization", "stage"], name="idx_leads_org_stage"),
            models.Index(fields=["organization", "email"], name="idx_leads_org_email"),
            models.Index(fields=["organization", "phone"], name="idx_leads_org_phone"),
        ]

    def __str__(self):
        return f"Lead #{self.pk} ({self.stage})"


class LeadTag(TimeStampedModel, OrgScopedModel):
    """No deleted_at per ERD §7 — pure M2M join, nothing to soft-delete."""

    lead = models.ForeignKey(Lead, on_delete=models.CASCADE, related_name="lead_tags")
    tag = models.ForeignKey(Tag, on_delete=models.CASCADE, related_name="lead_tags")

    objects = OrgScopedNoSoftDeleteManager()
    unscoped = UnscopedManager()

    class Meta:
        db_table = "lead_tags"
        constraints = [
            models.UniqueConstraint(fields=["lead", "tag"], name="uniq_lead_tag"),
        ]


class LeadStageHistoryQuerySet(BaseQuerySet):
    def for_current_organization(self):
        return self.filter(lead__organization_id=get_current_organization())


class LeadStageHistoryManager(models.Manager.from_queryset(LeadStageHistoryQuerySet)):
    """LeadStageHistory has no organization_id column of its own (ERD §8
    deliberately omits it — reachable via lead_id -> lead.organization_id,
    avoiding a denormalized duplicate column). Scoped via the Lead
    relation instead of a direct organization filter."""

    def get_queryset(self):
        return super().get_queryset().for_current_organization()


class LeadStageHistory(models.Model):
    """Append-only per Domain Model §8 / ERD §8 — no deleted_at, no
    update/delete exposed at the application layer, ever."""

    lead = models.ForeignKey(Lead, on_delete=models.CASCADE, related_name="stage_history")
    from_stage = models.CharField(max_length=20, choices=LeadStage.choices, null=True, blank=True)
    to_stage = models.CharField(max_length=20, choices=LeadStage.choices)
    changed_by = models.ForeignKey(
        "organizations.Membership",
        on_delete=models.PROTECT,
        related_name="lead_stage_changes",
    )
    changed_at = models.DateTimeField(db_default=Now(), editable=False)
    reason = models.TextField(null=True, blank=True)

    objects = LeadStageHistoryManager()
    unscoped = models.Manager()

    class Meta:
        db_table = "lead_stage_history"
        indexes = [
            models.Index(fields=["lead", "changed_at"], name="idx_lsh_lead_changed"),
        ]

    def __str__(self):
        return f"Lead #{self.lead_id}: {self.from_stage} -> {self.to_stage}"
    