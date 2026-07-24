from django.urls import path

from apps.activities.views import ActivityDetailView, ActivityListCreateView

urlpatterns = [
    path("<int:organization_id>/activities/", ActivityListCreateView.as_view(), name="activity-list-create"),
    path("<int:organization_id>/activities/<int:activity_id>/", ActivityDetailView.as_view(), name="activity-detail"),
]
