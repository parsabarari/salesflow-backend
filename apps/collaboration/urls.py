from django.urls import path

from apps.collaboration.views import (
    AttachmentCreateView, AttachmentDetailView, AttachmentRestoreView,
    CommentDetailView, CommentListCreateView, CommentRestoreView,
)

urlpatterns = [
    path("<int:organization_id>/comments/", CommentListCreateView.as_view(), name="comment-list-create"),
    path("<int:organization_id>/comments/<int:comment_id>/", CommentDetailView.as_view(), name="comment-detail"),
    path("<int:organization_id>/comments/<int:comment_id>/restore/", CommentRestoreView.as_view(), name="comment-restore"),
    path("<int:organization_id>/attachments/", AttachmentCreateView.as_view(), name="attachment-create"),
    path("<int:organization_id>/attachments/<int:attachment_id>/", AttachmentDetailView.as_view(), name="attachment-detail"),
    path("<int:organization_id>/attachments/<int:attachment_id>/restore/", AttachmentRestoreView.as_view(), name="attachment-restore"),
]
