from django.urls import path

from apps.dashboard.views import DashboardSummaryView

urlpatterns = [
    path("<int:organization_id>/dashboard/summary/", DashboardSummaryView.as_view(), name="dashboard-summary"),
]
