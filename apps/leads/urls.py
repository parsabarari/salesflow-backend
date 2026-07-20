from django.urls import path

from apps.leads.views import (LeadDetailView, LeadListCreateView,
                              LeadStageTransitionView, LeadTimelineView)

urlpatterns = [
    path("<int:organization_id>/leads/", LeadListCreateView.as_view(), name="lead-list-create"),
    path("<int:organization_id>/leads/<int:lead_id>/", LeadDetailView.as_view(), name="lead-detail"),
    path("<int:organization_id>/leads/<int:lead_id>/stage/", LeadStageTransitionView.as_view(), name="lead-stage-transition"),
    path("<int:organization_id>/leads/<int:lead_id>/timeline/", LeadTimelineView.as_view(), name="lead-timeline"),
]
