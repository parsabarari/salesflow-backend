from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from django.http import Http404
from drf_spectacular.utils import extend_schema, extend_schema_view

from apps.core.permissions import get_active_membership
from apps.core.views import OrgScopedViewSetMixin
from apps.notifications.models import Notification
from apps.notifications.serializers import NotificationSerializer
from apps.notifications.services import NotificationService


@extend_schema_view(get=extend_schema(tags=["Notifications"]))
class NotificationListView(OrgScopedViewSetMixin, APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, organization_id):
        membership = get_active_membership(request)
        queryset = Notification.objects.filter(recipient_membership=membership)

        is_read = request.query_params.get("is_read")
        if is_read is not None:
            queryset = queryset.filter(is_read=is_read.lower() == "true")

        queryset = queryset.order_by("-created_at")
        return Response(NotificationSerializer(queryset, many=True).data)


@extend_schema_view(post=extend_schema(tags=["Notifications"]))
class NotificationMarkReadView(OrgScopedViewSetMixin, APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, organization_id, notification_id):
        membership = get_active_membership(request)
        try:
            notification = Notification.objects.get(id=notification_id, recipient_membership=membership)
        except Notification.DoesNotExist:
            raise Http404()
        notification = NotificationService.mark_read(notification)
        return Response(NotificationSerializer(notification).data)


@extend_schema_view(post=extend_schema(tags=["Notifications"]))
class NotificationMarkAllReadView(OrgScopedViewSetMixin, APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, organization_id):
        membership = get_active_membership(request)
        updated_count = NotificationService.mark_all_read(membership)
        return Response({"updated_count": updated_count}, status=status.HTTP_200_OK)
