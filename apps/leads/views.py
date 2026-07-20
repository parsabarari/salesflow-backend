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
from apps.core.viewsets import RoleScopedQuerysetMixin
from apps.leads.models import Lead
from apps.leads.serializers import (
    LeadCreateSerializer, LeadSerializer, LeadStageTransitionSerializer, LeadUpdateSerializer,
)
from apps.leads.services import LeadDuplicateService, LeadService, LeadStageTransitionService, assert_can_assign_owner
from apps.organizations.models import Membership, MembershipRole

# PRD 5.3 matrix, Leads column. Support Agent has no Lead access ("—").
# Viewer clarified as org-wide read-only (see conversation decision —
# recommend recording this in docs/02-business-rules.md §3 once confirmed).
LEAD_ROLE_SCOPE_MAP = {
    MembershipRole.OWNER: SCOPE_FULL,
    MembershipRole.ADMIN: SCOPE_FULL,
    MembershipRole.SALES_MANAGER: SCOPE_TEAM,
    MembershipRole.SALES_AGENT: SCOPE_OWN,
    MembershipRole.SUPPORT_AGENT: SCOPE_NONE,
    MembershipRole.VIEWER: SCOPE_READONLY_ORG,
}


def _resolve_owner(owner_id):
    try:
        return Membership.objects.get(id=owner_id)
    except Membership.DoesNotExist:
        raise ValueError("Invalid owner_id.")


class LeadListCreateView(OrgScopedViewSetMixin, RoleScopedQuerysetMixin, APIView):
    permission_classes = [IsAuthenticated, RoleMatrixPermission]
    role_scope_map = LEAD_ROLE_SCOPE_MAP
    owner_field = "owner"

    def get_base_queryset(self):
        # Business Rules 4.1: archived Leads excluded from default list
        # views. (?include_archived=true filter param: deferred — flagging
        # as an open item, not yet implemented in this step.)
        return Lead.objects.filter(is_archived=False)

    def get(self, request, organization_id):
        return Response(LeadSerializer(self.get_queryset(), many=True).data)

    def post(self, request, organization_id):
        serializer = LeadCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            target_owner = _resolve_owner(data["owner_id"])
            assert_can_assign_owner(
                actor_membership=request.membership, target_owner=target_owner, scope=request.rbac_scope,
            )
        except ValueError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        lead = LeadService.create_lead(
            organization=request.membership.organization,
            owner=target_owner,
            source=data["source"],
            email=data.get("email"),
            phone=data.get("phone"),
        )

        possible_duplicates = LeadDuplicateService.find_possible_duplicates(
            email=lead.email, phone=lead.phone, exclude_lead_id=lead.id,
        )
        response_data = LeadSerializer(lead).data
        response_data["possible_duplicates"] = possible_duplicates  # Business Rules 4.3
        return Response(response_data, status=status.HTTP_201_CREATED)


class LeadDetailView(OrgScopedViewSetMixin, RoleScopedQuerysetMixin, APIView):
    permission_classes = [IsAuthenticated, RoleMatrixPermission]
    role_scope_map = LEAD_ROLE_SCOPE_MAP
    owner_field = "owner"

    def get_base_queryset(self):
        return Lead.objects.all()  # archived Leads still individually reachable by ID

    def _get_object(self, lead_id):
        try:
            return self.get_queryset().get(id=lead_id)
        except Lead.DoesNotExist:
            raise Http404()

    def get(self, request, organization_id, lead_id):
        return Response(LeadSerializer(self._get_object(lead_id)).data)

    def patch(self, request, organization_id, lead_id):
        if request.rbac_scope == SCOPE_READONLY_ORG:
            return Response(status=status.HTTP_403_FORBIDDEN)

        lead = self._get_object(lead_id)
        serializer = LeadUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        if "owner_id" in data:
            try:
                target_owner = _resolve_owner(data.pop("owner_id"))
                assert_can_assign_owner(
                    actor_membership=request.membership, target_owner=target_owner, scope=request.rbac_scope,
                )
            except ValueError as e:
                return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
            data["owner"] = target_owner

        possible_duplicates = None
        if "email" in data or "phone" in data:
            possible_duplicates = LeadDuplicateService.find_possible_duplicates(
                email=data.get("email", lead.email),
                phone=data.get("phone", lead.phone),
                exclude_lead_id=lead.id,
            )

        for field, value in data.items():
            setattr(lead, field, value)
        lead.save(update_fields=list(data.keys()))

        response_data = LeadSerializer(lead).data
        if possible_duplicates is not None:
            response_data["possible_duplicates"] = possible_duplicates
        return Response(response_data)

    def delete(self, request, organization_id, lead_id):
        if request.rbac_scope == SCOPE_READONLY_ORG:
            return Response(status=status.HTTP_403_FORBIDDEN)
        lead = self._get_object(lead_id)
        lead.is_archived = True
        lead.deleted_at = timezone.now()
        lead.save(update_fields=["is_archived", "deleted_at"])
        return Response(status=status.HTTP_204_NO_CONTENT)


class LeadStageTransitionView(OrgScopedViewSetMixin, RoleScopedQuerysetMixin, APIView):
    permission_classes = [IsAuthenticated, RoleMatrixPermission]
    role_scope_map = LEAD_ROLE_SCOPE_MAP
    owner_field = "owner"

    def get_base_queryset(self):
        return Lead.objects.all()

    def post(self, request, organization_id, lead_id):
        if request.rbac_scope == SCOPE_READONLY_ORG:
            return Response(status=status.HTTP_403_FORBIDDEN)

        try:
            lead = self.get_queryset().get(id=lead_id)
        except Lead.DoesNotExist:
            raise Http404()

        serializer = LeadStageTransitionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            lead = LeadStageTransitionService.transition(
                lead=lead, to_stage=data["to_stage"], changed_by=request.membership, reason=data.get("reason"),
            )
        except ValueError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(LeadSerializer(lead).data)
