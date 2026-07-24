from rest_framework import serializers

from apps.activities.models import Activity, ActivityStatus, ActivityType


class ActivitySerializer(serializers.ModelSerializer):
    assignee_id = serializers.IntegerField(read_only=True)
    parent_type = serializers.SerializerMethodField()
    parent_id = serializers.IntegerField(source="parent_object_id", read_only=True)

    class Meta:
        model = Activity
        fields = ["id", "type", "assignee_id", "parent_type", "parent_id", "due_date", "status", "created_at"]
        validators = []

    def get_parent_type(self, obj):
        return obj.parent_content_type.model  # "lead" or "customer"


class ActivityCreateSerializer(serializers.Serializer):
    parent_type = serializers.ChoiceField(choices=["lead", "customer"])
    parent_id = serializers.IntegerField()
    assignee_id = serializers.IntegerField()
    type = serializers.ChoiceField(choices=ActivityType.choices)
    due_date = serializers.DateTimeField()


class ActivityUpdateSerializer(serializers.Serializer):
    assignee_id = serializers.IntegerField(required=False)
    type = serializers.ChoiceField(choices=ActivityType.choices, required=False)
    due_date = serializers.DateTimeField(required=False)
    # Only the two forward transitions are ever valid input (Business
    # Rules 8.1); "pending" is never a target of a client-issued update.
    status = serializers.ChoiceField(
        choices=[ActivityStatus.COMPLETED, ActivityStatus.CANCELLED], required=False
    )

    def validate(self, attrs):
        if not attrs:
            raise serializers.ValidationError("Provide at least one field to update.")
        return attrs
