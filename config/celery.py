import logging
import os

from celery import Celery
from celery.schedules import crontab
from celery.signals import task_failure

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")

app = Celery("salesflow")

app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()


app.conf.beat_schedule = {
    "expire-pending-invitations": {
        "task": "apps.organizations.tasks.expire_pending_invitations_task",
        "schedule": crontab(minute=0, hour=0),  # daily at midnight — docs/06-architecture.md §3
    },
    "activity-due-soon-and-overdue-sweep": {
        "task": "apps.activities.tasks.activity_due_soon_and_overdue_sweep_task",
        "schedule": crontab(minute="*/15"),
    },
}


celery_logger = logging.getLogger("apps.core.celery")


@task_failure.connect
def log_task_failure(sender=None, task_id=None, exception=None, args=None, kwargs=None, einfo=None, **extra):
    """docs/06-architecture.md §7 — "Celery job failures must surface
    somewhere an operator will see them (specific APM/error-tracking
    product is an implementation choice, left open)." This is the
    product-agnostic minimum: every task failure lands in structured
    logs with full context, regardless of whether/which APM tool is
    added later. Fires for every task across every queue automatically
    — no per-task wiring needed."""
    celery_logger.error(
        "celery_task_failure",
        extra={
            "task_name": getattr(sender, "name", None),
            "task_id": task_id,
            "task_args": args,
            "task_kwargs": kwargs,
            "exception": str(exception),
            "traceback": str(einfo) if einfo else None,
        },
    )