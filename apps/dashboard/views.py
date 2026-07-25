from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.views import OrgScopedViewSetMixin
from apps.dashboard.services import DashboardService


class DashboardSummaryView(OrgScopedViewSetMixin, APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, organization_id):
        summary = DashboardService.get_summary(organization_id)
        return Response(summary)
