from rest_framework import serializers

from apps.audit.models import AuditLog


class AuditLogSerializer(serializers.ModelSerializer):
    actor_membership_id = serializers.IntegerField(read_only=True)
    target_type = serializers.SerializerMethodField()
    target_id = serializers.IntegerField(source="target_object_id", read_only=True)

    class Meta:
        model = AuditLog
        fields = ["id", "actor_membership_id", "action_type", "target_type", "target_id", "metadata", "created_at"]
        validators = []

    def get_target_type(self, obj):
        return obj.target_content_type.model
