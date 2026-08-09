from django.urls import path

from apps.activities.views import ActivityDetailView, ActivityListCreateView, ActivityRestoreView

urlpatterns = [
    path("<int:organization_id>/activities/", ActivityListCreateView.as_view(), name="activity-list-create"),
    path("<int:organization_id>/activities/<int:activity_id>/", ActivityDetailView.as_view(), name="activity-detail"),
    path("<int:organization_id>/activities/<int:activity_id>/restore/", ActivityRestoreView.as_view(), name="activity-restore"),
]
