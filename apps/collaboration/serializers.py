from rest_framework import serializers

from apps.collaboration.models import Attachment, Comment


class CommentSerializer(serializers.ModelSerializer):
    author_id = serializers.IntegerField(read_only=True)
    parent_type = serializers.SerializerMethodField()
    parent_id = serializers.IntegerField(source="parent_object_id", read_only=True)
    mentioned_membership_ids = serializers.SerializerMethodField()

    class Meta:
        model = Comment
        fields = ["id", "author_id", "parent_type", "parent_id", "body", "mentioned_membership_ids", "created_at"]
        validators = []

    def get_parent_type(self, obj):
        return obj.parent_content_type.model

    def get_mentioned_membership_ids(self, obj):
        return list(obj.mentions.values_list("mentioned_membership_id", flat=True))


class CommentCreateSerializer(serializers.Serializer):
    parent_type = serializers.ChoiceField(choices=["lead", "customer", "ticket"])
    parent_id = serializers.IntegerField()
    body = serializers.CharField()


class CommentUpdateSerializer(serializers.Serializer):
    body = serializers.CharField()


class AttachmentSerializer(serializers.ModelSerializer):
    uploaded_by_id = serializers.IntegerField(read_only=True)
    parent_type = serializers.SerializerMethodField()
    parent_id = serializers.IntegerField(source="parent_object_id", read_only=True)

    class Meta:
        model = Attachment
        fields = [
            "id", "uploaded_by_id", "parent_type", "parent_id",
            "original_filename", "file_size_bytes", "created_at",
        ]
        validators = []

    def get_parent_type(self, obj):
        return obj.parent_content_type.model
