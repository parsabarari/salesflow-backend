from rest_framework.response import Response
from rest_framework.views import APIView

from apps.audit.models import AuditLog
from apps.audit.serializers import AuditLogSerializer
from apps.core.permissions import IsOwnerOrAdmin
from apps.core.views import OrgScopedViewSetMixin
from rest_framework.permissions import IsAuthenticated


class AuditLogListView(OrgScopedViewSetMixin, APIView):
    permission_classes = [IsAuthenticated, IsOwnerOrAdmin]

    def get(self, request, organization_id):
        queryset = AuditLog.objects.all().order_by("-created_at")
        params = request.query_params

        if params.get("action_type"):
            queryset = queryset.filter(action_type=params["action_type"])
        if params.get("actor"):
            queryset = queryset.filter(actor_membership_id=params["actor"])
        if params.get("created_at__gte"):
            queryset = queryset.filter(created_at__gte=params["created_at__gte"])
        if params.get("created_at__lte"):
            queryset = queryset.filter(created_at__lte=params["created_at__lte"])

        return Response(AuditLogSerializer(queryset, many=True).data)
