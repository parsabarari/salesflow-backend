from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from django.http import Http404
from drf_spectacular.utils import extend_schema

from apps.core.permissions import IsOwnerOrAdmin
from apps.core.views import OrgScopedViewSetMixin
from apps.organizations.models import Invitation, Membership
from apps.organizations.serializers import (
    AcceptInvitationSerializer,
    CreateInvitationSerializer,
    InvitationSerializer,
    MembershipSerializer,
    UpdateMembershipSerializer,
)
from apps.organizations.services import InvitationService, MembershipService


class InvitationListCreateView(OrgScopedViewSetMixin, APIView):
    permission_classes = [IsAuthenticated, IsOwnerOrAdmin]

    @extend_schema(responses={200: InvitationSerializer(many=True)})
    def get(self, request, organization_id):
        invitations = Invitation.objects.all()
        return Response(InvitationSerializer(invitations, many=True).data)

    @extend_schema(request=CreateInvitationSerializer, responses={201: InvitationSerializer})
    def post(self, request, organization_id):
        serializer = CreateInvitationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            invitation = InvitationService.create(
                organization=request.membership.organization,
                invited_by_membership=request.membership,
                **serializer.validated_data,
            )
        except ValueError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        from apps.organizations.tasks import send_invitation_email_task
        send_invitation_email_task.delay(invitation.id)
        return Response(InvitationSerializer(invitation).data, status=status.HTTP_201_CREATED)


class InvitationResendView(OrgScopedViewSetMixin, APIView):
    permission_classes = [IsAuthenticated, IsOwnerOrAdmin]

    @extend_schema(responses={200: InvitationSerializer})
    def post(self, request, organization_id, invitation_id):
        invitation = Invitation.objects.get(id=invitation_id)
        InvitationService.resend(invitation)
        return Response(InvitationSerializer(invitation).data)


class MembershipDetailView(OrgScopedViewSetMixin, APIView):
    permission_classes = [IsAuthenticated, IsOwnerOrAdmin]

    def _get_target(self, membership_id):
        try:
            return Membership.objects.get(id=membership_id, deleted_at__isnull=True)
        except Membership.DoesNotExist:
            raise Http404()

    @extend_schema(request=UpdateMembershipSerializer, responses={200: MembershipSerializer})
    def patch(self, request, organization_id, membership_id):
        target_membership = self._get_target(membership_id)
        serializer = UpdateMembershipSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            if "role" in data:
                MembershipService.change_role(
                    actor_membership=request.membership,
                    target_membership=target_membership,
                    new_role=data["role"],
                )
            if "reports_to" in data:
                reports_to_membership = (
                    self._get_target(data["reports_to"]) if data["reports_to"] is not None else None
                )
                MembershipService.change_reports_to(
                    actor_membership=request.membership,
                    target_membership=target_membership,
                    reports_to_membership=reports_to_membership,
                )
        except ValueError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        target_membership.refresh_from_db()
        return Response(MembershipSerializer(target_membership).data)

    def delete(self, request, organization_id, membership_id):
        target_membership = self._get_target(membership_id)
        try:
            MembershipService.remove(
                actor_membership=request.membership,
                target_membership=target_membership,
            )
        except ValueError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(status=status.HTTP_204_NO_CONTENT)


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
    