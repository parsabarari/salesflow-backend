from django.contrib.contenttypes.models import ContentType
from django.http import Http404
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.activities.models import Activity
from apps.activities.serializers import (
    ActivityCreateSerializer,
    ActivitySerializer,
    ActivityUpdateSerializer,
)
from apps.activities.services import PARENT_MODEL_MAP, ActivityService
from apps.core.permissions import (
    RoleMatrixPermission,
    SCOPE_FULL,
    SCOPE_OWN,
    SCOPE_READONLY_ORG,
    SCOPE_TEAM,
)
from apps.core.views import OrgScopedViewSetMixin
from apps.core.viewsets import RoleScopedQuerysetMixin
from apps.organizations.models import Membership, MembershipRole

# PRD 5.3 matrix, Activities column.
#
# Support Agent's matrix cell reads "Own only (ticket-related)" — but
# Activity's parent is restricted to Lead/Customer only (Business Rules
# 8.2, Domain Model §15); there is no Ticket linkage on this model at
# all, so the "ticket-related" qualifier isn't expressible as written.
# Treating Support Agent as plain SCOPE_OWN (their own assigned
# Activities) here, same as Sales Agent. Flagging this as an open
# question for docs/02-business-rules.md rather than silently deciding
# it's fully resolved — not yet written down anywhere.
#
# Viewer: org-wide read-only, consistent with the Viewer decision
# already applied to Leads (see apps/leads/views.py).
ACTIVITY_ROLE_SCOPE_MAP = {
    MembershipRole.OWNER: SCOPE_FULL,
    MembershipRole.ADMIN: SCOPE_FULL,
    MembershipRole.SALES_MANAGER: SCOPE_TEAM,
    MembershipRole.SALES_AGENT: SCOPE_OWN,
    MembershipRole.SUPPORT_AGENT: SCOPE_OWN,
    MembershipRole.VIEWER: SCOPE_READONLY_ORG,
}


class ActivityObjectLookupMixin(RoleScopedQuerysetMixin):
    owner_field = "assignee"

    def get_base_queryset(self):
        return Activity.objects.all()

    def _get_object(self, activity_id):
        try:
            return self.get_queryset().get(id=activity_id)
        except Activity.DoesNotExist:
            raise Http404()


class ActivityListCreateView(OrgScopedViewSetMixin, ActivityObjectLookupMixin, APIView):
    permission_classes = [IsAuthenticated, RoleMatrixPermission]
    role_scope_map = ACTIVITY_ROLE_SCOPE_MAP

    def get_base_queryset(self):
        queryset = Activity.objects.all()
        params = self.request.query_params

        if params.get("type"):
            queryset = queryset.filter(type=params["type"])
        if params.get("status"):
            queryset = queryset.filter(status=params["status"])
        if params.get("assignee"):
            queryset = queryset.filter(assignee_id=params["assignee"])
        if params.get("due_date__gte"):
            queryset = queryset.filter(due_date__gte=params["due_date__gte"])
        if params.get("due_date__lte"):
            queryset = queryset.filter(due_date__lte=params["due_date__lte"])

        parent_type = params.get("parent_type")
        parent_id = params.get("parent_id")
        # API Spec §7: parent_type and parent_id are required together
        # when filtering by parent — an Activity always has exactly one
        # parent (Business Rules 8.2), so a filter naming only one of
        # the two is an incomplete/ambiguous request, not a valid filter.
        if bool(parent_type) != bool(parent_id):
            raise ValueError("parent_type and parent_id must be provided together.")
        if parent_type and parent_id:
            model = PARENT_MODEL_MAP.get(parent_type)
            if model is None:
                raise ValueError("parent_type must be 'lead' or 'customer'.")
            content_type = ContentType.objects.get_for_model(model)
            queryset = queryset.filter(parent_content_type=content_type, parent_object_id=parent_id)

        return queryset

    def get(self, request, organization_id):
        try:
            queryset = self.get_queryset()
        except ValueError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(ActivitySerializer(queryset, many=True).data)

    def post(self, request, organization_id):
        serializer = ActivityCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            assignee = Membership.objects.get(id=data["assignee_id"])
        except Membership.DoesNotExist:
            return Response({"detail": "Invalid assignee_id."}, status=status.HTTP_400_BAD_REQUEST)

        # SCOPE_OWN roles (Sales Agent, Support Agent) may only create
        # Activities assigned to themselves — same guard already applied
        # to Lead ownership in apps/leads/views.py.
        if request.rbac_scope == SCOPE_OWN and assignee.id != request.membership.id:
            return Response(
                {"detail": "You can only create activities assigned to yourself."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            activity = ActivityService.create(
                organization=request.membership.organization,
                parent_type=data["parent_type"],
                parent_id=data["parent_id"],
                assignee=assignee,
                activity_type=data["type"],
                due_date=data["due_date"],
            )
        except ValueError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(ActivitySerializer(activity).data, status=status.HTTP_201_CREATED)


class ActivityDetailView(OrgScopedViewSetMixin, ActivityObjectLookupMixin, APIView):
    permission_classes = [IsAuthenticated, RoleMatrixPermission]
    role_scope_map = ACTIVITY_ROLE_SCOPE_MAP

    def get(self, request, organization_id, activity_id):
        activity = self._get_object(activity_id)
        return Response(ActivitySerializer(activity).data)

    def patch(self, request, organization_id, activity_id):
        activity = self._get_object(activity_id)
        serializer = ActivityUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        if (
            request.rbac_scope == SCOPE_OWN
            and "assignee_id" in data
            and data["assignee_id"] != request.membership.id
        ):
            return Response(
                {"detail": "You can only reassign an activity to yourself."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        fields = {}
        if "assignee_id" in data:
            try:
                fields["assignee"] = Membership.objects.get(id=data["assignee_id"])
            except Membership.DoesNotExist:
                return Response({"detail": "Invalid assignee_id."}, status=status.HTTP_400_BAD_REQUEST)
        if "type" in data:
            fields["type"] = data["type"]
        if "due_date" in data:
            fields["due_date"] = data["due_date"]

        try:
            if fields:
                activity = ActivityService.update_fields(activity, **fields)
            if "status" in data:
                activity = ActivityService.update_status(activity, data["status"])
        except ValueError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(ActivitySerializer(activity).data)

    def delete(self, request, organization_id, activity_id):
        activity = self._get_object(activity_id)
        activity.delete()  # soft delete (SoftDeleteModel.delete())
        return Response(status=status.HTTP_204_NO_CONTENT)
