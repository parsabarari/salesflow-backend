from django.urls import path

from apps.organizations.views import (
    InvitationAcceptView,
    InvitationListCreateView,
    InvitationResendView,
)

urlpatterns = [
    path("<int:organization_id>/invitations/", InvitationListCreateView.as_view(), name="invitation-list-create"),
    path("<int:organization_id>/invitations/<int:invitation_id>/resend/", InvitationResendView.as_view(), name="invitation-resend"),
]
