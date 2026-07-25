from django.urls import path

from apps.collaboration.views import (
    AttachmentCreateView, AttachmentDetailView, CommentDetailView, CommentListCreateView,
)

urlpatterns = [
    path("<int:organization_id>/comments/", CommentListCreateView.as_view(), name="comment-list-create"),
    path("<int:organization_id>/comments/<int:comment_id>/", CommentDetailView.as_view(), name="comment-detail"),
    path("<int:organization_id>/attachments/", AttachmentCreateView.as_view(), name="attachment-create"),
    path("<int:organization_id>/attachments/<int:attachment_id>/", AttachmentDetailView.as_view(), name="attachment-detail"),
]
