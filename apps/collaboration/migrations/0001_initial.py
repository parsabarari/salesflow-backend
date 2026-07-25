import django.db.models.deletion
import django.db.models.functions.datetime
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('contenttypes', '0002_remove_content_type_name'),
        ('organizations', '0002_alter_invitation_organization_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='Comment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(db_default=django.db.models.functions.datetime.Now(), editable=False)),
                ('deleted_at', models.DateTimeField(blank=True, null=True)),
                ('parent_object_id', models.BigIntegerField()),
                ('body', models.TextField()),
                ('author', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='comments', to='organizations.membership')),
                ('organization', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='%(app_label)s_%(class)s_set', to='organizations.organization')),
                ('parent_content_type', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='+', to='contenttypes.contenttype')),
            ],
            options={
                'db_table': 'comments',
            },
        ),
        migrations.CreateModel(
            name='Attachment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(db_default=django.db.models.functions.datetime.Now(), editable=False)),
                ('deleted_at', models.DateTimeField(blank=True, null=True)),
                ('parent_object_id', models.BigIntegerField()),
                ('file_reference', models.CharField(max_length=500)),
                ('original_filename', models.CharField(max_length=255)),
                ('file_size_bytes', models.BigIntegerField()),
                ('organization', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='%(app_label)s_%(class)s_set', to='organizations.organization')),
                ('parent_content_type', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='+', to='contenttypes.contenttype')),
                ('uploaded_by', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='attachments', to='organizations.membership')),
            ],
            options={
                'db_table': 'attachments',
            },
        ),
        migrations.CreateModel(
            name='CommentMention',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('comment', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='mentions', to='collaboration.comment')),
                ('mentioned_membership', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='comment_mentions', to='organizations.membership')),
            ],
            options={
                'db_table': 'comment_mentions',
            },
        ),
        migrations.AddIndex(
            model_name='comment',
            index=models.Index(fields=['parent_content_type', 'parent_object_id', 'created_at'], name='idx_comments_parent_created'),
        ),
        migrations.AddIndex(
            model_name='attachment',
            index=models.Index(fields=['parent_content_type', 'parent_object_id'], name='idx_attachments_parent'),
        ),
        migrations.AddConstraint(
            model_name='attachment',
            constraint=models.CheckConstraint(condition=models.Q(('file_size_bytes__gte', 0)), name='attachments_size_non_negative'),
        ),
        migrations.AddIndex(
            model_name='commentmention',
            index=models.Index(fields=['mentioned_membership', 'created_at'], name='idx_cm_membership_created'),
        ),
    ]
