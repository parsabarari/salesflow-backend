from django.http import Http404
from rest_framework.exceptions import NotAuthenticated
from rest_framework.permissions import IsAuthenticated

from apps.core.context import clear_current_organization, set_current_organization
from apps.organizations.models import Membership


class OrgScopedViewSetMixin:
    organization_url_kwarg = "organization_id"
    permission_classes = [IsAuthenticated]

    def initial(self, request, *args, **kwargs):
        # Accessing request.user triggers DRF's lazy authentication —
        # safe to do before super().initial() runs it again as part of
        # check_permissions(). We check it explicitly here because the
        # membership lookup below needs a real User, not AnonymousUser,
        # and Django's ORM raises ValueError (not a clean 401) if you
        # filter a ForeignKey against AnonymousUser.
        if not request.user or not request.user.is_authenticated:
            raise NotAuthenticated()

        organization_id = int(kwargs[self.organization_url_kwarg])
        if not Membership.unscoped.filter(
            user=request.user,
            organization_id=organization_id,
            deleted_at__isnull=True,
        ).exists():
            raise Http404()

        # Context must be set BEFORE super().initial(), since that call
        # runs check_permissions() — and permission classes like
        # IsOwnerOrAdmin query Membership.objects (org-scoped), which
        # requires the context to already be set.
        set_current_organization(organization_id)
        super().initial(request, *args, **kwargs)

    def finalize_response(self, request, response, *args, **kwargs):
        try:
            return super().finalize_response(request, response, *args, **kwargs)
        finally:
            clear_current_organization()