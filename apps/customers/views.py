from django.http import Http404
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.permissions import (
    RoleMatrixPermission, SCOPE_FULL, SCOPE_NONE, SCOPE_OWN, SCOPE_READONLY_ORG, SCOPE_TEAM,
)
from apps.core.views import OrgScopedViewSetMixin
from apps.customers.models import Contact, Customer
from apps.customers.serializers import (
    ContactCreateSerializer, ContactSerializer, CustomerSerializer, CustomerUpdateSerializer,
)
from apps.customers.services import ContactService
from apps.organizations.models import MembershipRole
from apps.organizations.services import TeamService

# PRD 5.3 matrix, Customers column. Sales Agent's "Read (own leads'
# customers)" doesn't fit the generic owner_field-based RoleScopedQuerysetMixin
# (Customer has no owner field — reached only via CustomerLeadLink back
# to whichever Lead(s) won it, Business Rules 6.2). Handled with bespoke
# filtering below rather than forcing it into that mixin.
CUSTOMER_ROLE_SCOPE_MAP = {
    MembershipRole.OWNER: SCOPE_FULL,
    MembershipRole.ADMIN: SCOPE_FULL,
    MembershipRole.SALES_MANAGER: SCOPE_TEAM,
    MembershipRole.SALES_AGENT: SCOPE_OWN,  # bespoke meaning here, see get_queryset below
    MembershipRole.SUPPORT_AGENT: SCOPE_READONLY_ORG,
    MembershipRole.VIEWER: SCOPE_READONLY_ORG,
}


class CustomerListView(OrgScopedViewSetMixin, APIView):
    permission_classes = [IsAuthenticated, RoleMatrixPermission]
    role_scope_map = CUSTOMER_ROLE_SCOPE_MAP

    def get(self, request, organization_id):
        queryset = Customer.objects.all()
        scope = request.rbac_scope
        membership = request.membership

        if scope in (SCOPE_FULL, SCOPE_READONLY_ORG):
            pass
        elif scope == SCOPE_OWN:
            # ASSUMPTION (flagging, not a copy of an existing pattern):
            # "own leads' customers" = Customers reached via at least
            # one CustomerLeadLink to a Lead this Agent owns.
            queryset = queryset.filter(lead_links__lead__owner=membership).distinct()
        elif scope == SCOPE_TEAM:
            team_ids = TeamService.team_membership_ids(membership) + [membership.id]
            queryset = queryset.filter(lead_links__lead__owner_id__in=team_ids).distinct()
        else:
            queryset = queryset.none()

        return Response(CustomerSerializer(queryset, many=True).data)


class CustomerDetailView(OrgScopedViewSetMixin, APIView):
    permission_classes = [IsAuthenticated, RoleMatrixPermission]
    role_scope_map = CUSTOMER_ROLE_SCOPE_MAP

    def _get_object(self, request, customer_id):
        try:
            customer = Customer.objects.get(id=customer_id)
        except Customer.DoesNotExist:
            raise Http404()

        scope = request.rbac_scope
        if scope in (SCOPE_FULL, SCOPE_READONLY_ORG):
            return customer
        if scope == SCOPE_OWN:
            if customer.lead_links.filter(lead__owner=request.membership).exists():
                return customer
            raise Http404()
        if scope == SCOPE_TEAM:
            team_ids = TeamService.team_membership_ids(request.membership) + [request.membership.id]
            if customer.lead_links.filter(lead__owner_id__in=team_ids).exists():
                return customer
            raise Http404()
        raise Http404()

    def get(self, request, organization_id, customer_id):
        return Response(CustomerSerializer(self._get_object(request, customer_id)).data)

    def patch(self, request, organization_id, customer_id):
        if request.rbac_scope in (SCOPE_READONLY_ORG, SCOPE_NONE):
            return Response(status=status.HTTP_403_FORBIDDEN)
        customer = self._get_object(request, customer_id)
        serializer = CustomerUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        for field, value in serializer.validated_data.items():
            setattr(customer, field, value)
        customer.save(update_fields=list(serializer.validated_data.keys()))
        return Response(CustomerSerializer(customer).data)

    def delete(self, request, organization_id, customer_id):
        if request.rbac_scope in (SCOPE_READONLY_ORG, SCOPE_NONE):
            return Response(status=status.HTTP_403_FORBIDDEN)
        customer = self._get_object(request, customer_id)
        customer.deleted_at = timezone.now()
        customer.save(update_fields=["deleted_at"])
        return Response(status=status.HTTP_204_NO_CONTENT)


class ContactListCreateView(OrgScopedViewSetMixin, APIView):
    permission_classes = [IsAuthenticated, RoleMatrixPermission]
    role_scope_map = CUSTOMER_ROLE_SCOPE_MAP

    def _get_customer(self, request, customer_id):
        return CustomerDetailView()._get_object(request, customer_id)  # reuse the same visibility check

    def get(self, request, organization_id, customer_id):
        customer = self._get_customer(request, customer_id)
        return Response(ContactSerializer(customer.contacts.all(), many=True).data)

    def post(self, request, organization_id, customer_id):
        if request.rbac_scope in (SCOPE_READONLY_ORG, SCOPE_NONE):
            return Response(status=status.HTTP_403_FORBIDDEN)
        customer = self._get_customer(request, customer_id)
        serializer = ContactCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        contact = ContactService.create(customer=customer, **serializer.validated_data)
        return Response(ContactSerializer(contact).data, status=status.HTTP_201_CREATED)


class ContactDetailView(OrgScopedViewSetMixin, APIView):
    permission_classes = [IsAuthenticated, RoleMatrixPermission]
    role_scope_map = CUSTOMER_ROLE_SCOPE_MAP

    def _get_object(self, request, contact_id):
        try:
            contact = Contact.objects.get(id=contact_id)
        except Contact.DoesNotExist:
            raise Http404()
        CustomerDetailView()._get_object(request, contact.customer_id)  # raises Http404 if customer not visible
        return contact

    def patch(self, request, organization_id, contact_id):
        if request.rbac_scope in (SCOPE_READONLY_ORG, SCOPE_NONE):
            return Response(status=status.HTTP_403_FORBIDDEN)
        contact = self._get_object(request, contact_id)
        serializer = ContactCreateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        for field, value in serializer.validated_data.items():
            setattr(contact, field, value)
        contact.save(update_fields=list(serializer.validated_data.keys()))
        return Response(ContactSerializer(contact).data)

    def delete(self, request, organization_id, contact_id):
        if request.rbac_scope in (SCOPE_READONLY_ORG, SCOPE_NONE):
            return Response(status=status.HTTP_403_FORBIDDEN)
        contact = self._get_object(request, contact_id)
        try:
            ContactService.remove(contact=contact)
        except ValueError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(status=status.HTTP_204_NO_CONTENT)
