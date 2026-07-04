import django.db.models.functions.datetime
from django.contrib.postgres.operations import CITextExtension
from django.db import migrations, models

import apps.core.models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("auth", "0012_alter_user_first_name_max_length"),
    ]

    operations = [
        CITextExtension(),
        migrations.CreateModel(
            name="User",
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
                ("password", models.CharField(db_column="password_hash", max_length=128, verbose_name="password")),
                ("email", apps.core.models.CIEmailField(max_length=254, unique=True)),
                ("is_email_verified", models.BooleanField(default=False)),
                (
                    "created_at",
                    models.DateTimeField(
                        db_default=django.db.models.functions.datetime.Now(),
                        editable=False,
                    ),
                ),
            ],
            options={
                "db_table": "users",
            },
        ),
    ]
