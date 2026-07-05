from django.db import models
from django.db.models import Q

from apps.core.models import (CIEmailField, OrgScopedModel, 
                              SoftDeleteModel, TimeStampedModel,)
from apps.core.managers import (OrgScopedManager, OrgScopedAllManager,
                                OrgScopedNoSoftDeleteManager, UnscopedManager)


class MembershipRole(models.TextChoices):
    OWNER = "owner", "Owner"
    ADMIN = "admin", "Admin"
    SALES_MANAGER = "sales_manager", "Sales Manager"
    SALES_AGENT = "sales_agent", "Sales Agent"
    SUPPORT_AGENT = "support_agent", "Support Agent"
    VIEWER = "viewer", "Viewer"


class Organization(TimeStampedModel, SoftDeleteModel):
    name = models.CharField(max_length=255)
    settings = models.JSONField(default=dict)

    class Meta:
        db_table = "organizations"

    def __str__(self):
        return self.name


class Membership(TimeStampedModel, SoftDeleteModel, OrgScopedModel):
    Role = MembershipRole

    user = models.ForeignKey(
        "accounts.User",
        on_delete=models.PROTECT,
        related_name="memberships",
    )
    role = models.CharField(max_length=20, choices=Role.choices)
    reports_to = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="direct_reports",
    )

    objects = OrgScopedManager()
    all_objects = OrgScopedAllManager()
    unscoped = UnscopedManager()

    class Meta:
        db_table = "memberships"
        constraints = [
            models.UniqueConstraint(
                fields=["user", "organization"],
                condition=Q(deleted_at__isnull=True),
                name="uniq_active_membership_user_organization",
            ),
            models.CheckConstraint(
                condition=Q(role__in=MembershipRole.values),
                name="memberships_role_valid",
            ),
        ]
        indexes = [
            models.Index(fields=["organization", "role"], name="idx_memberships_org_role"),
            models.Index(fields=["reports_to"], name="idx_memberships_reports_to"),
        ]

    def __str__(self):
        return f"{self.user.email} @ {self.organization_id}"


class Invitation(TimeStampedModel, OrgScopedModel):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        ACCEPTED = "accepted", "Accepted"
        EXPIRED = "expired", "Expired"
        REVOKED = "revoked", "Revoked"

    email = CIEmailField()
    role = models.CharField(max_length=20, choices=MembershipRole.choices)
    invited_by = models.ForeignKey(
        Membership,
        on_delete=models.PROTECT,
        related_name="sent_invitations",
    )
    token = models.CharField(max_length=64, unique=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    expires_at = models.DateTimeField()

    objects = OrgScopedNoSoftDeleteManager()
    
    class Meta:
        db_table = "invitations"
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "email"],
                condition=Q(status="pending"),
                name="uniq_pending_invitation_organization_email",
            ),
            models.CheckConstraint(
                condition=Q(role__in=MembershipRole.values),
                name="invitations_role_valid",
            ),
            models.CheckConstraint(
                condition=Q(status__in=[
                    "pending",
                    "accepted",
                    "expired",
                    "revoked",
                    ]),
                name="invitations_status_valid",
            ),
        ]

    def __str__(self):
        return f"{self.email} -> {self.organization_id}"



