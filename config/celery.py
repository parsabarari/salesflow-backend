import os

from celery import Celery
from celery.schedules import crontab

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")

app = Celery("salesflow")

app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()


app.conf.beat_schedule = {
    "expire-pending-invitations": {
        "task": "apps.organizations.tasks.expire_pending_invitations_task",
        "schedule": crontab(hour="*/1"),
    },
}
