from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_spectacular.utils import extend_schema, extend_schema_view

from apps.core.views import OrgScopedViewSetMixin
from apps.dashboard.services import DashboardService


@extend_schema_view(get=extend_schema(tags=["Dashboard"]))
class DashboardSummaryView(OrgScopedViewSetMixin, APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, organization_id):
        summary = DashboardService.get_summary(organization_id)
        return Response(summary)
