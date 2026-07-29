from django.contrib.contenttypes.models import ContentType
from django.http import Http404
from rest_framework import status, serializers as drf_serializers
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiTypes, inline_serializer

from apps.collaboration.models import Attachment, Comment
from apps.collaboration.permissions import resolve_parent_scope
from apps.collaboration.serializers import (
    AttachmentSerializer, CommentCreateSerializer, CommentSerializer, CommentUpdateSerializer,
)
from apps.collaboration.services import (
    ATTACHMENT_PARENT_MODEL_MAP, COMMENT_PARENT_MODEL_MAP, AttachmentService, CommentService,
)
from apps.core.permissions import SCOPE_NONE, SCOPE_READONLY_ORG, get_active_membership
from apps.core.services import resolve_polymorphic_parent
from apps.core.views import OrgScopedViewSetMixin
from apps.organizations.models import MembershipRole


@extend_schema_view(
    get=extend_schema(tags=["Collaboration"]),
    post=extend_schema(tags=["Collaboration"], request=CommentCreateSerializer),
)
class CommentListCreateView(OrgScopedViewSetMixin, APIView):
    permission_classes = [IsAuthenticated]

    def _resolve_parent_and_scope(self, request, parent_type, parent_id):
        parent = resolve_polymorphic_parent(
            model_map=COMMENT_PARENT_MODEL_MAP,
            parent_type=parent_type,
            parent_id=parent_id,
            organization_id=request.membership.organization_id,
        )
        scope = resolve_parent_scope(membership=request.membership, role=request.membership.role, parent=parent)
        return parent, scope

    def get(self, request, organization_id):
        request.membership = get_active_membership(request)
        parent_type = request.query_params.get("parent_type")
        parent_id = request.query_params.get("parent_id")
        if bool(parent_type) != bool(parent_id):
            return Response({"detail": "parent_type and parent_id must be provided together."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            parent, scope = self._resolve_parent_and_scope(request, parent_type, parent_id)
        except ValueError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        if scope == SCOPE_NONE:
            raise Http404()

        content_type = ContentType.objects.get_for_model(parent.__class__)
        comments = Comment.objects.filter(parent_content_type=content_type, parent_object_id=parent.id)
        return Response(CommentSerializer(comments, many=True).data)

    def post(self, request, organization_id):
        request.membership = get_active_membership(request)
        serializer = CommentCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            parent, scope = self._resolve_parent_and_scope(request, data["parent_type"], data["parent_id"])
        except ValueError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        if scope == SCOPE_NONE:
            raise Http404()
        if scope == SCOPE_READONLY_ORG:
            return Response(status=status.HTTP_403_FORBIDDEN)

        comment = CommentService.create(
            organization=request.membership.organization,
            parent_type=data["parent_type"],
            parent_id=data["parent_id"],
            author=request.membership,
            body=data["body"],
        )
        return Response(CommentSerializer(comment).data, status=status.HTTP_201_CREATED)


@extend_schema_view(
    get=extend_schema(tags=["Collaboration"]),
    patch=extend_schema(tags=["Collaboration"], request=CommentUpdateSerializer),
    delete=extend_schema(tags=["Collaboration"]),
)
class CommentDetailView(OrgScopedViewSetMixin, APIView):
    permission_classes = [IsAuthenticated]

    def _get_visible_comment(self, request, comment_id):
        try:
            comment = Comment.objects.get(id=comment_id)
        except Comment.DoesNotExist:
            raise Http404()
        parent_model = comment.parent_content_type.model_class()
        parent = parent_model.all_objects.get(id=comment.parent_object_id)
        scope = resolve_parent_scope(membership=request.membership, role=request.membership.role, parent=parent)
        if scope == SCOPE_NONE:
            raise Http404()
        return comment

    def get(self, request, organization_id, comment_id):
        request.membership = get_active_membership(request)
        comment = self._get_visible_comment(request, comment_id)
        return Response(CommentSerializer(comment).data)

    def patch(self, request, organization_id, comment_id):
        request.membership = get_active_membership(request)
        comment = self._get_visible_comment(request, comment_id)
        # API Spec §9: author or Owner/Admin only.
        if comment.author_id != request.membership.id and request.membership.role not in (
            MembershipRole.OWNER, MembershipRole.ADMIN,
        ):
            return Response(status=status.HTTP_403_FORBIDDEN)

        serializer = CommentUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        comment = CommentService.update_body(comment, serializer.validated_data["body"])
        return Response(CommentSerializer(comment).data)

    def delete(self, request, organization_id, comment_id):
        request.membership = get_active_membership(request)
        comment = self._get_visible_comment(request, comment_id)
        if comment.author_id != request.membership.id and request.membership.role not in (
            MembershipRole.OWNER, MembershipRole.ADMIN,
        ):
            return Response(status=status.HTTP_403_FORBIDDEN)
        comment.delete()  # soft delete
        return Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema_view(
    post=extend_schema(
        tags=["Collaboration"],
        request={
            "multipart/form-data": inline_serializer(
                name="AttachmentUpload",
                fields={
                    "parent_type": drf_serializers.ChoiceField(choices=["lead", "customer"]),
                    "parent_id": drf_serializers.IntegerField(),
                    "file": drf_serializers.FileField(),
                },
            )
        },
    ),
)
class AttachmentCreateView(OrgScopedViewSetMixin, APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request, organization_id):
        request.membership = get_active_membership(request)
        parent_type = request.data.get("parent_type")
        parent_id = request.data.get("parent_id")
        uploaded_file = request.FILES.get("file")
        if not parent_type or not parent_id or not uploaded_file:
            return Response({"detail": "parent_type, parent_id, and file are required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            parent = resolve_polymorphic_parent(
                model_map=ATTACHMENT_PARENT_MODEL_MAP,
                parent_type=parent_type,
                parent_id=parent_id,
                organization_id=request.membership.organization_id,
            )
        except ValueError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        scope = resolve_parent_scope(membership=request.membership, role=request.membership.role, parent=parent)
        if scope == SCOPE_NONE:
            raise Http404()
        if scope == SCOPE_READONLY_ORG:
            return Response(status=status.HTTP_403_FORBIDDEN)

        attachment = AttachmentService.create(
            organization=request.membership.organization,
            parent_type=parent_type,
            parent_id=parent_id,
            uploaded_by=request.membership,
            uploaded_file=uploaded_file,
        )
        return Response(AttachmentSerializer(attachment).data, status=status.HTTP_201_CREATED)


@extend_schema_view(get=extend_schema(tags=["Collaboration"]), delete=extend_schema(tags=["Collaboration"]))
class AttachmentDetailView(OrgScopedViewSetMixin, APIView):
    permission_classes = [IsAuthenticated]

    def _get_visible_attachment(self, request, attachment_id):
        try:
            attachment = Attachment.objects.get(id=attachment_id)
        except Attachment.DoesNotExist:
            raise Http404()
        parent_model = attachment.parent_content_type.model_class()
        parent = parent_model.all_objects.get(id=attachment.parent_object_id)
        scope = resolve_parent_scope(membership=request.membership, role=request.membership.role, parent=parent)
        if scope == SCOPE_NONE:
            raise Http404()
        return attachment

    def get(self, request, organization_id, attachment_id):
        request.membership = get_active_membership(request)
        attachment = self._get_visible_attachment(request, attachment_id)
        data = AttachmentSerializer(attachment).data
        data["url"] = AttachmentService.get_signed_url(attachment)
        return Response(data)

    def delete(self, request, organization_id, attachment_id):
        request.membership = get_active_membership(request)
        attachment = self._get_visible_attachment(request, attachment_id)
        attachment.delete()  # soft delete
        return Response(status=status.HTTP_204_NO_CONTENT)
