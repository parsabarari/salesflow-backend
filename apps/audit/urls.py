from django.urls import path

from apps.audit.views import AuditLogListView

urlpatterns = [
    path("<int:organization_id>/audit-logs/", AuditLogListView.as_view(), name="audit-log-list"),
]
