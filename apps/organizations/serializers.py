from rest_framework import serializers

from apps.organizations.models import Invitation, MembershipRole


class CreateInvitationSerializer(serializers.Serializer):
    email = serializers.EmailField()
    role = serializers.ChoiceField(choices=MembershipRole.choices)


class InvitationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Invitation
        fields = ["id", "email", "role", "status", "expires_at", "created_at"]
        validators = []
        

class AcceptInvitationSerializer(serializers.Serializer):
    password = serializers.CharField(write_only=True, min_length=8)
