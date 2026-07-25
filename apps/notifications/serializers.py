from rest_framework import serializers

from apps.notifications.models import Notification


class NotificationSerializer(serializers.ModelSerializer):
    related_type = serializers.SerializerMethodField()
    related_id = serializers.IntegerField(source="related_object_id", read_only=True)

    class Meta:
        model = Notification
        fields = ["id", "type", "related_type", "related_id", "is_read", "created_at"]
        validators = []

    def get_related_type(self, obj):
        return obj.related_content_type.model
