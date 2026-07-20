from rest_framework import serializers

from apps.leads.models import Lead, LeadStage, Tag


class TagSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tag
        fields = ["id", "name"]
        validators = []


class LeadSerializer(serializers.ModelSerializer):
    owner_id = serializers.IntegerField(source="owner.id", read_only=True)
    tag_ids = serializers.PrimaryKeyRelatedField(source="tags", many=True, read_only=True)

    class Meta:
        model = Lead
        fields = [
            "id", "owner_id", "source", "email", "phone", "stage", "lost_reason",
            "is_archived", "requires_manual_customer_selection", "tag_ids", "created_at",
        ]
        read_only_fields = ["stage", "lost_reason", "requires_manual_customer_selection", "created_at"]
        validators = []


class LeadCreateSerializer(serializers.Serializer):
    owner_id = serializers.IntegerField()
    source = serializers.CharField(max_length=100)
    email = serializers.EmailField(required=False, allow_null=True)
    phone = serializers.CharField(max_length=30, required=False, allow_null=True)

    def validate(self, attrs):
        if not attrs.get("email") and not attrs.get("phone"):
            raise serializers.ValidationError("At least one of email or phone is required.")  # Business Rules 4.2
        return attrs


class LeadUpdateSerializer(serializers.Serializer):
    owner_id = serializers.IntegerField(required=False)
    source = serializers.CharField(max_length=100, required=False)
    email = serializers.EmailField(required=False, allow_null=True)
    phone = serializers.CharField(max_length=30, required=False, allow_null=True)
    is_archived = serializers.BooleanField(required=False)

    def validate(self, attrs):
        if not attrs:
            raise serializers.ValidationError("Provide at least one field to update.")
        return attrs


class LeadStageTransitionSerializer(serializers.Serializer):
    to_stage = serializers.ChoiceField(choices=LeadStage.choices)
    reason = serializers.CharField(required=False, allow_blank=True, allow_null=True)


class LeadTimelineEventSerializer(serializers.Serializer):
    type = serializers.CharField()
    occurred_at = serializers.DateTimeField()
    data = serializers.DictField()
