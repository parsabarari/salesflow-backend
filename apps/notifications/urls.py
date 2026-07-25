from django.urls import path

from apps.notifications.views import (
    NotificationListView, NotificationMarkAllReadView, NotificationMarkReadView,
)

urlpatterns = [
    path("<int:organization_id>/notifications/", NotificationListView.as_view(), name="notification-list"),
    path("<int:organization_id>/notifications/<int:notification_id>/read/", NotificationMarkReadView.as_view(), name="notification-mark-read"),
    path("<int:organization_id>/notifications/read-all/", NotificationMarkAllReadView.as_view(), name="notification-mark-all-read"),
]
