class OrganizationScopedQuerysetMixin:
    organization_url_kwarg = "organization_id"

    def get_queryset(self):
        queryset = super().get_queryset()
        organization_id = self.kwargs[self.organization_url_kwarg]
        return queryset.for_organization(organization_id)
