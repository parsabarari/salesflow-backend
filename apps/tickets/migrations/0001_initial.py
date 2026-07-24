import django.db.models.deletion
import django.db.models.functions.datetime
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('customers', '0001_initial'),
        ('organizations', '0002_alter_invitation_organization_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='Ticket',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(db_default=django.db.models.functions.datetime.Now(), editable=False)),
                ('deleted_at', models.DateTimeField(blank=True, null=True)),
                ('subject', models.CharField(max_length=255)),
                ('priority', models.CharField(choices=[('low', 'Low'), ('medium', 'Medium'), ('high', 'High'), ('urgent', 'Urgent')], default='medium', max_length=20)),
                ('status', models.CharField(choices=[('open', 'Open'), ('in_progress', 'In Progress'), ('resolved', 'Resolved'), ('closed', 'Closed'), ('reopened', 'Reopened')], default='open', max_length=20)),
                ('assignee', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='assigned_tickets', to='organizations.membership')),
                ('contact', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='tickets', to='customers.contact')),
                ('created_by', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='created_tickets', to='organizations.membership')),
                ('customer', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='tickets', to='customers.customer')),
                ('organization', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='%(app_label)s_%(class)s_set', to='organizations.organization')),
            ],
            options={
                'db_table': 'tickets',
            },
        ),
        migrations.AddIndex(
            model_name='ticket',
            index=models.Index(fields=['organization', 'assignee'], name='idx_tickets_org_assignee'),
        ),
        migrations.AddIndex(
            model_name='ticket',
            index=models.Index(fields=['organization', 'status'], name='idx_tickets_org_status'),
        ),
        migrations.AddIndex(
            model_name='ticket',
            index=models.Index(fields=['customer'], name='idx_tickets_customer'),
        ),
        migrations.AddConstraint(
            model_name='ticket',
            constraint=models.CheckConstraint(condition=models.Q(('priority__in', ['low', 'medium', 'high', 'urgent'])), name='tickets_priority_valid'),
        ),
        migrations.AddConstraint(
            model_name='ticket',
            constraint=models.CheckConstraint(condition=models.Q(('status__in', ['open', 'in_progress', 'resolved', 'closed', 'reopened'])), name='tickets_status_valid'),
        ),
    ]
