from django.urls import path

from apps.organizations.views import (
    InvitationAcceptView,
    InvitationListCreateView,
    InvitationResendView,
    MembershipDetailView,
)

urlpatterns = [
    path("<int:organization_id>/invitations/", InvitationListCreateView.as_view(), name="invitation-list-create"),
    path("<int:organization_id>/invitations/<int:invitation_id>/resend/", InvitationResendView.as_view(), name="invitation-resend"),
    path("<int:organization_id>/memberships/<int:membership_id>/", MembershipDetailView.as_view(), name="membership-detail"),

]
