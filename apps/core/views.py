from django.http import Http404
from rest_framework.viewsets import ViewSetMixin

from apps.core.context import clear_current_organization, set_current_organization
from apps.organizations.models import Membership


class OrgScopedViewSetMixin(ViewSetMixin):
    organization_url_kwarg = "organization_id"

    def initial(self, request, *args, **kwargs):
        organization_id = int(kwargs[self.organization_url_kwarg])
        if not Membership.unscoped.filter(
            user=request.user,
            organization_id=organization_id,
            deleted_at__isnull=True,
        ).exists():
            raise Http404()
        set_current_organization(organization_id)
        super().initial(request, *args, **kwargs)

    def finalize_response(self, request, response, *args, **kwargs):
        try:
            return super().finalize_response(request, response, *args, **kwargs)
        finally:
            clear_current_organization()
