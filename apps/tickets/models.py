from django.db import models
from django.db.models import Q

from apps.core.managers import OrgScopedAllManager, OrgScopedManager, UnscopedManager
from apps.core.models import OrgScopedModel, SoftDeleteModel, TimeStampedModel


class TicketPriority(models.TextChoices):
    LOW = "low", "Low"
    MEDIUM = "medium", "Medium"
    HIGH = "high", "High"
    URGENT = "urgent", "Urgent"


class TicketStatus(models.TextChoices):
    OPEN = "open", "Open"
    IN_PROGRESS = "in_progress", "In Progress"
    RESOLVED = "resolved", "Resolved"
    CLOSED = "closed", "Closed"
    REOPENED = "reopened", "Reopened"


class Ticket(TimeStampedModel, SoftDeleteModel, OrgScopedModel):
    Priority = TicketPriority
    Status = TicketStatus

    # Business Rules 7.1: no Ticket can exist without a resolved Customer
    # link — customer_id is required, never nullable.
    customer = models.ForeignKey(
        "customers.Customer",
        on_delete=models.PROTECT,
        related_name="tickets",
    )
    # Optional: a Ticket can be scoped to a specific Contact of that
    # Customer, or left at the Customer level (ERD §16). The invariant
    # "contact.customer_id == this.customer_id" is a cross-column check,
    # not expressible as a plain CHECK constraint — enforced in
    # TicketService (next chunk), matching the ERD §16 note.
    contact = models.ForeignKey(
        "customers.Contact",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="tickets",
    )
    subject = models.CharField(max_length=255)
    priority = models.CharField(max_length=20, choices=Priority.choices, default=Priority.MEDIUM)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.OPEN)
    assignee = models.ForeignKey(
        "organizations.Membership",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="assigned_tickets",
    )
    created_by = models.ForeignKey(
        "organizations.Membership",
        on_delete=models.PROTECT,
        related_name="created_tickets",
    )

    objects = OrgScopedManager()
    all_objects = OrgScopedAllManager()
    unscoped = UnscopedManager()

    class Meta:
        db_table = "tickets"
        constraints = [
            models.CheckConstraint(
                condition=Q(priority__in=TicketPriority.values),
                name="tickets_priority_valid",
            ),
            models.CheckConstraint(
                condition=Q(status__in=TicketStatus.values),
                name="tickets_status_valid",
            ),
        ]
        indexes = [
            models.Index(fields=["organization", "assignee"], name="idx_tickets_org_assignee"),
            models.Index(fields=["organization", "status"], name="idx_tickets_org_status"),
            models.Index(fields=["customer"], name="idx_tickets_customer"),
        ]

    def __str__(self):
        return f"Ticket #{self.pk}: {self.subject} ({self.status})"
