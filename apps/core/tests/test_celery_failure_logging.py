import logging

from celery.signals import task_failure
from django.test import SimpleTestCase


class CeleryTaskFailureLoggingTests(SimpleTestCase):
    """Verifies the task_failure signal handler itself (config/celery.py)
    logs structured failure details — exercised directly rather than via
    a real failing task, since eager-mode signal timing/propagation
    behavior is a Celery implementation detail we don't want this test
    coupled to."""

    def test_failure_signal_logs_structured_details(self):
        with self.assertLogs("apps.core.celery", level="ERROR") as cm:
            task_failure.send(
                sender=type("FakeTask", (), {"name": "apps.fake.tasks.explode"})(),
                task_id="abc-123",
                exception=ValueError("boom"),
                args=(1, 2),
                kwargs={"x": "y"},
                einfo="Traceback (most recent call last): ...",
            )

        self.assertEqual(len(cm.records), 1)
        record = cm.records[0]
        self.assertEqual(record.task_name, "apps.fake.tasks.explode")
        self.assertEqual(record.task_id, "abc-123")
        self.assertEqual(record.exception, "boom")
        self.assertIn("Traceback", record.traceback)
