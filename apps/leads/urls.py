from django.urls import path

from apps.leads.views import (
    LeadDetailView, LeadListCreateView, LeadStageTransitionView, LeadTagAttachView,
    LeadTimelineView, TagListCreateView, LeadResolveCustomerView, 
)

urlpatterns = [
    path("<int:organization_id>/leads/", LeadListCreateView.as_view(), name="lead-list-create"),
    path("<int:organization_id>/leads/<int:lead_id>/", LeadDetailView.as_view(), name="lead-detail"),
    path("<int:organization_id>/leads/<int:lead_id>/stage/", LeadStageTransitionView.as_view(), name="lead-stage-transition"),
    path("<int:organization_id>/leads/<int:lead_id>/timeline/", LeadTimelineView.as_view(), name="lead-timeline"),
    path("<int:organization_id>/leads/<int:lead_id>/tags/", LeadTagAttachView.as_view(), name="lead-tag-attach"),
    path("<int:organization_id>/leads/<int:lead_id>/tags/<int:tag_id>/", LeadTagAttachView.as_view(), name="lead-tag-detach"),
    path("<int:organization_id>/tags/", TagListCreateView.as_view(), name="tag-list-create"),
    path("<int:organization_id>/leads/<int:lead_id>/resolve-customer/", LeadResolveCustomerView.as_view(), name="lead-resolve-customer"),
]
