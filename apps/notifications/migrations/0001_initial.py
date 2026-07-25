import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('contenttypes', '0002_remove_content_type_name'),
        ('organizations', '0002_alter_invitation_organization_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='Notification',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('type', models.CharField(choices=[('lead_assigned', 'Lead Assigned'), ('lead_stage_changed', 'Lead Stage Changed'), ('comment_mention', 'Comment Mention'), ('ticket_assigned', 'Ticket Assigned'), ('ticket_status_changed', 'Ticket Status Changed'), ('activity_due_soon', 'Activity Due Soon'), ('activity_overdue', 'Activity Overdue')], max_length=40)),
                ('related_object_id', models.BigIntegerField()),
                ('is_read', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('recipient_membership', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='notifications', to='organizations.membership')),
                ('related_content_type', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='+', to='contenttypes.contenttype')),
            ],
            options={
                'db_table': 'notifications',
            },
        ),
        migrations.AddIndex(
            model_name='notification',
            index=models.Index(fields=['recipient_membership', 'is_read', 'created_at'], name='idx_ntf_recipient_read_created'),
        ),
        migrations.AddConstraint(
            model_name='notification',
            constraint=models.CheckConstraint(condition=models.Q(('type__in', ['lead_assigned', 'lead_stage_changed', 'comment_mention', 'ticket_assigned', 'ticket_status_changed', 'activity_due_soon', 'activity_overdue'])), name='notifications_type_valid'),
        ),
    ]
