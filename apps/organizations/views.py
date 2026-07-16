from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_spectacular.utils import extend_schema

from apps.core.views import OrgScopedViewSetMixin
from apps.organizations.models import Invitation, Membership, MembershipRole
from apps.organizations.serializers import (
    AcceptInvitationSerializer,
    CreateInvitationSerializer,
    InvitationSerializer,
)
from apps.organizations.services import InvitationService


class InvitationListCreateView(OrgScopedViewSetMixin, APIView):
    def _require_owner_or_admin(self, request):
        # موقت: تا وقتی permission class واقعی در فاز ۱.۲ ساخته شود.
        membership = Membership.objects.get(user=request.user)
        if membership.role not in (MembershipRole.OWNER, MembershipRole.ADMIN):
            return False
        return membership

    @extend_schema(responses={200: InvitationSerializer(many=True)})
    def get(self, request, organization_id):
        if not self._require_owner_or_admin(request):
            return Response(status=status.HTTP_403_FORBIDDEN)
        invitations = Invitation.objects.all()
        return Response(InvitationSerializer(invitations, many=True).data)

    @extend_schema(request=CreateInvitationSerializer, responses={201: InvitationSerializer})
    def post(self, request, organization_id):
        membership = self._require_owner_or_admin(request)
        if not membership:
            return Response(status=status.HTTP_403_FORBIDDEN)
        serializer = CreateInvitationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            invitation = InvitationService.create(
                organization=membership.organization,
                invited_by_membership=membership,
                **serializer.validated_data,
            )
        except ValueError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        from apps.organizations.tasks import send_invitation_email_task
        send_invitation_email_task.delay(invitation.id)
        return Response(InvitationSerializer(invitation).data, status=status.HTTP_201_CREATED)


class InvitationResendView(OrgScopedViewSetMixin, APIView):
    @extend_schema(responses={200: InvitationSerializer})
    def post(self, request, organization_id, invitation_id):
        membership = Membership.objects.get(user=request.user)
        if membership.role not in (MembershipRole.OWNER, MembershipRole.ADMIN):
            return Response(status=status.HTTP_403_FORBIDDEN)
        invitation = Invitation.objects.get(id=invitation_id)
        InvitationService.resend(invitation)
        return Response(InvitationSerializer(invitation).data)


class InvitationAcceptView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(request=AcceptInvitationSerializer, responses={200: dict})
    def post(self, request, token):
        serializer = AcceptInvitationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            membership = InvitationService.accept(
                token=token,
                password=serializer.validated_data["password"],
            )
        except ValueError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            {"organization_id": membership.organization_id, "role": membership.role},
            status=status.HTTP_200_OK,
        )
    