from django.urls import path
from rest_framework import viewsets
from rest_framework.response import Response

from apps.core.views import OrgScopedViewSetMixin


class ProbeViewSet(OrgScopedViewSetMixin, viewsets.ViewSet):
    def list(self, request, organization_id=None):
        return Response({"ok": True})


urlpatterns = [
    path(
        "api/v1/organizations/<int:organization_id>/probe/",
        ProbeViewSet.as_view({"get": "list"}),
    ),
]
