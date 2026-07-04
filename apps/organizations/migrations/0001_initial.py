import django.db.models.deletion
import django.db.models.functions.datetime
from django.conf import settings
from django.db import migrations, models

import apps.core.models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Organization",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "created_at",
                    models.DateTimeField(
                        db_default=django.db.models.functions.datetime.Now(),
                        editable=False,
                    ),
                ),
                ("deleted_at", models.DateTimeField(blank=True, null=True)),
                ("name", models.CharField(max_length=255)),
                ("settings", models.JSONField(default=dict)),
            ],
            options={
                "db_table": "organizations",
            },
        ),
        migrations.CreateModel(
            name="Membership",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "created_at",
                    models.DateTimeField(
                        db_default=django.db.models.functions.datetime.Now(),
                        editable=False,
                    ),
                ),
                ("deleted_at", models.DateTimeField(blank=True, null=True)),
                (
                    "role",
                    models.CharField(
                        choices=[
                            ("owner", "Owner"),
                            ("admin", "Admin"),
                            ("sales_manager", "Sales Manager"),
                            ("sales_agent", "Sales Agent"),
                            ("support_agent", "Support Agent"),
                            ("viewer", "Viewer"),
                        ],
                        max_length=20,
                    ),
                ),
                (
                    "organization",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="organizations_membership_set",
                        to="organizations.organization",
                    ),
                ),
                (
                    "reports_to",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="direct_reports",
                        to="organizations.membership",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="memberships",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "db_table": "memberships",
            },
        ),
        migrations.CreateModel(
            name="Invitation",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "created_at",
                    models.DateTimeField(
                        db_default=django.db.models.functions.datetime.Now(),
                        editable=False,
                    ),
                ),
                ("email", apps.core.models.CIEmailField(max_length=254)),
                (
                    "role",
                    models.CharField(
                        choices=[
                            ("owner", "Owner"),
                            ("admin", "Admin"),
                            ("sales_manager", "Sales Manager"),
                            ("sales_agent", "Sales Agent"),
                            ("support_agent", "Support Agent"),
                            ("viewer", "Viewer"),
                        ],
                        max_length=20,
                    ),
                ),
                ("token", models.CharField(max_length=64, unique=True)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "Pending"),
                            ("accepted", "Accepted"),
                            ("expired", "Expired"),
                            ("revoked", "Revoked"),
                        ],
                        default="pending",
                        max_length=20,
                    ),
                ),
                ("expires_at", models.DateTimeField()),
                (
                    "invited_by",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="sent_invitations",
                        to="organizations.membership",
                    ),
                ),
                (
                    "organization",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="organizations_invitation_set",
                        to="organizations.organization",
                    ),
                ),
            ],
            options={
                "db_table": "invitations",
            },
        ),
        migrations.AddConstraint(
            model_name="membership",
            constraint=models.UniqueConstraint(
                condition=models.Q(("deleted_at__isnull", True)),
                fields=("user", "organization"),
                name="uniq_active_membership_user_organization",
            ),
        ),
        migrations.AddConstraint(
            model_name="membership",
            constraint=models.CheckConstraint(
                condition=models.Q(("role__in", ["owner", "admin", "sales_manager", "sales_agent", "support_agent", "viewer"])),
                name="memberships_role_valid",
            ),
        ),
        migrations.AddIndex(
            model_name="membership",
            index=models.Index(fields=["organization", "role"], name="idx_memberships_org_role"),
        ),
        migrations.AddIndex(
            model_name="membership",
            index=models.Index(fields=["reports_to"], name="idx_memberships_reports_to"),
        ),
        migrations.AddConstraint(
            model_name="invitation",
            constraint=models.UniqueConstraint(
                condition=models.Q(("status", "pending")),
                fields=("organization", "email"),
                name="uniq_pending_invitation_organization_email",
            ),
        ),
        migrations.AddConstraint(
            model_name="invitation",
            constraint=models.CheckConstraint(
                condition=models.Q(("role__in", ["owner", "admin", "sales_manager", "sales_agent", "support_agent", "viewer"])),
                name="invitations_role_valid",
            ),
        ),
        migrations.AddConstraint(
            model_name="invitation",
            constraint=models.CheckConstraint(
                condition=models.Q(("status__in", ["pending", "accepted", "expired", "revoked"])),
                name="invitations_status_valid",
            ),
        ),
    ]
