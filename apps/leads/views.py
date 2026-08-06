from django.http import Http404
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework import status, serializers as drf_serializers
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_spectacular.utils import extend_schema, extend_schema_view, inline_serializer

from apps.core.permissions import (
    RoleMatrixPermission, SCOPE_FULL, SCOPE_NONE, SCOPE_OWN, SCOPE_READONLY_ORG, SCOPE_TEAM,
)
from apps.core.views import IdempotentPostMixin, OrgScopedViewSetMixin
from apps.core.viewsets import RoleScopedQuerysetMixin
from apps.core.permissions import IsOwnerOrAdmin, get_active_membership  # reused loosely below, see note
from apps.leads.models import Lead, Tag
from apps.leads.serializers import (LeadCreateSerializer, LeadSerializer,
                                    LeadStageTransitionSerializer, LeadUpdateSerializer,
                                    LeadTimelineEventSerializer, TagCreateSerializer,
                                    TagSerializer, ResolveCustomerSerializer,)
from apps.leads.services import (LeadDuplicateService, LeadService,
                                 LeadStageTransitionService, LeadTimelineService,
                                 TagService, assert_can_assign_owner,)
from apps.organizations.models import Membership, MembershipRole
from apps.customers.services import CustomerService
from apps.notifications.models import NotificationType
from apps.notifications.services import NotificationService

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
    

class LeadObjectLookupMixin(RoleScopedQuerysetMixin):
    """Shared by every view that operates on a single existing Lead
    (detail, stage-transition, timeline) — factored out since all three
    need identical 'fetch within my visible scope, or 404' logic."""

    def get_base_queryset(self):
        return Lead.objects.all()  # archived Leads still individually reachable by ID

    def _get_object(self, lead_id):
        try:
            return self.get_queryset().get(id=lead_id)
        except Lead.DoesNotExist:
            raise Http404()


@extend_schema_view(
    get=extend_schema(tags=["Leads"]),
    patch=extend_schema(tags=["Leads"], request=LeadUpdateSerializer),
    delete=extend_schema(tags=["Leads"]),
)
class LeadDetailView(OrgScopedViewSetMixin, LeadObjectLookupMixin, APIView):
    permission_classes = [IsAuthenticated, RoleMatrixPermission]
    role_scope_map = LEAD_ROLE_SCOPE_MAP
    owner_field = "owner"

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


        if "owner" in data:
            NotificationService.create(
                recipient_membership=lead.owner, notification_type=NotificationType.LEAD_ASSIGNED, related_object=lead,
            )

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


@extend_schema_view(post=extend_schema(tags=["Leads"], request=LeadStageTransitionSerializer))
class LeadStageTransitionView(IdempotentPostMixin, OrgScopedViewSetMixin, LeadObjectLookupMixin, APIView):
    permission_classes = [IsAuthenticated, RoleMatrixPermission]
    role_scope_map = LEAD_ROLE_SCOPE_MAP
    owner_field = "owner"

    def _handle_idempotent_post(self, request, organization_id, lead_id):
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


@extend_schema_view(get=extend_schema(tags=["Leads"]))
class LeadTimelineView(OrgScopedViewSetMixin, LeadObjectLookupMixin, APIView):
    permission_classes = [IsAuthenticated, RoleMatrixPermission]
    role_scope_map = LEAD_ROLE_SCOPE_MAP
    owner_field = "owner"

    def get(self, request, organization_id, lead_id):
        lead = self._get_object(lead_id)
        events = LeadTimelineService.get_timeline(lead)
        return Response(LeadTimelineEventSerializer(events, many=True).data)
    

@extend_schema_view(
    get=extend_schema(tags=["Leads"]),
    post=extend_schema(tags=["Leads"], request=TagCreateSerializer),
)
class TagListCreateView(OrgScopedViewSetMixin, APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, organization_id):
        tags = Tag.objects.all()
        return Response(TagSerializer(tags, many=True).data)

    def post(self, request, organization_id):
        membership = get_active_membership(request)
        if membership is None or membership.role not in (
            MembershipRole.OWNER, MembershipRole.ADMIN, MembershipRole.SALES_MANAGER,
        ):
            return Response(status=status.HTTP_403_FORBIDDEN)

        serializer = TagCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            tag = TagService.create(organization=membership.organization, name=serializer.validated_data["name"])
        except ValueError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(TagSerializer(tag).data, status=status.HTTP_201_CREATED)


@extend_schema_view(
    post=extend_schema(
        tags=["Leads"],
        request=inline_serializer(name="AttachTag", fields={"tag_id": drf_serializers.IntegerField()}),
    ),
)
class LeadTagAttachView(OrgScopedViewSetMixin, LeadObjectLookupMixin, APIView):
    permission_classes = [IsAuthenticated, RoleMatrixPermission]
    role_scope_map = LEAD_ROLE_SCOPE_MAP
    owner_field = "owner"

    def post(self, request, organization_id, lead_id):
        if request.rbac_scope == SCOPE_READONLY_ORG:
            return Response(status=status.HTTP_403_FORBIDDEN)
        lead = self._get_object(lead_id)
        tag_id = request.data.get("tag_id")
        try:
            tag = Tag.objects.get(id=tag_id)
        except (Tag.DoesNotExist, TypeError, ValueError):
            return Response({"detail": "Invalid tag_id."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            TagService.attach(lead=lead, tag=tag)
        except ValueError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(status=status.HTTP_204_NO_CONTENT)

    def delete(self, request, organization_id, lead_id, tag_id):
        if request.rbac_scope == SCOPE_READONLY_ORG:
            return Response(status=status.HTTP_403_FORBIDDEN)
        lead = self._get_object(lead_id)
        TagService.detach(lead=lead, tag_id=tag_id)
        return Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema_view(post=extend_schema(tags=["Leads"], request=ResolveCustomerSerializer))
class LeadResolveCustomerView(OrgScopedViewSetMixin, LeadObjectLookupMixin, APIView):
    permission_classes = [IsAuthenticated, RoleMatrixPermission]
    role_scope_map = LEAD_ROLE_SCOPE_MAP
    owner_field = "owner"

    def post(self, request, organization_id, lead_id):
        if request.rbac_scope == SCOPE_READONLY_ORG:
            return Response(status=status.HTTP_403_FORBIDDEN)

        lead = self._get_object(lead_id)
        serializer = ResolveCustomerSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            CustomerService.resolve_manual_selection(lead=lead, customer_id=serializer.validated_data["customer_id"])
        except ValueError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        lead.refresh_from_db()
        return Response(LeadSerializer(lead).data)


@extend_schema_view(
    get=extend_schema(tags=["Leads"]),
    post=extend_schema(tags=["Leads"], request=LeadCreateSerializer),
)
class LeadListCreateView(OrgScopedViewSetMixin, RoleScopedQuerysetMixin, APIView):
    permission_classes = [IsAuthenticated, RoleMatrixPermission]
    role_scope_map = LEAD_ROLE_SCOPE_MAP
    owner_field = "owner"

    def get_base_queryset(self):
        params = self.request.query_params

        is_archived_param = params.get("is_archived")
        if is_archived_param is not None:
            queryset = Lead.objects.filter(is_archived=is_archived_param.lower() == "true")
        else:
            queryset = Lead.objects.filter(is_archived=False)

        if params.get("stage"):
            queryset = queryset.filter(stage=params["stage"])
        if params.get("owner"):
            queryset = queryset.filter(owner_id=params["owner"])
        if params.get("tags"):
            queryset = queryset.filter(tags__id=params["tags"]).distinct()
        if params.get("source"):
            queryset = queryset.filter(source=params["source"])

        created_gte = params.get("created_at__gte")
        if created_gte:
            parsed = parse_datetime(created_gte)
            if parsed:
                queryset = queryset.filter(created_at__gte=parsed)
        created_lte = params.get("created_at__lte")
        if created_lte:
            parsed = parse_datetime(created_lte)
            if parsed:
                queryset = queryset.filter(created_at__lte=parsed)

        ordering = params.get("ordering")
        if ordering and ordering.lstrip("-") in ("created_at", "stage"):
            queryset = queryset.order_by(ordering)

        return queryset

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
