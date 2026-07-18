from rest_framework import serializers

from apps.organizations.models import Invitation, MembershipRole, Membership


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


class MembershipSerializer(serializers.ModelSerializer):
    user_email = serializers.EmailField(source="user.email", read_only=True)

    class Meta:
        model = Membership
        fields = ["id", "user_email", "role", "reports_to", "created_at"]
        validators = []


class UpdateMembershipSerializer(serializers.Serializer):
    role = serializers.ChoiceField(choices=MembershipRole.choices, required=False)
    reports_to = serializers.IntegerField(required=False, allow_null=True)

    def validate(self, attrs):
        if not attrs:
            raise serializers.ValidationError("Provide at least one of: role, reports_to.")
        return attrs
