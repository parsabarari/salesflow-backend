from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.permissions import get_active_membership
from apps.core.views import OrgScopedViewSetMixin
from apps.search.services import SearchService


class GlobalSearchView(OrgScopedViewSetMixin, APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, organization_id):
        query = request.query_params.get("q", "").strip()
        if not query:
            return Response({"detail": "Query parameter 'q' is required."}, status=status.HTTP_400_BAD_REQUEST)

        membership = get_active_membership(request)
        results = SearchService.search(query=query, membership=membership, role=membership.role)
        return Response(results)
