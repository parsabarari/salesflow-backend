from rest_framework import serializers

from apps.tickets.models import Ticket, TicketPriority, TicketStatus


class TicketSerializer(serializers.ModelSerializer):
    customer_id = serializers.IntegerField(read_only=True)
    contact_id = serializers.IntegerField(read_only=True)
    assignee_id = serializers.IntegerField(read_only=True)
    created_by_id = serializers.IntegerField(read_only=True)

    class Meta:
        model = Ticket
        fields = [
            "id", "customer_id", "contact_id", "subject", "priority",
            "status", "assignee_id", "created_by_id", "created_at",
        ]
        read_only_fields = ["status", "created_at"]
        validators = []


class TicketCreateSerializer(serializers.Serializer):
    customer_id = serializers.IntegerField()
    contact_id = serializers.IntegerField(required=False, allow_null=True)
    subject = serializers.CharField(max_length=255)
    priority = serializers.ChoiceField(choices=TicketPriority.choices, required=False, default=TicketPriority.MEDIUM)
    assignee_id = serializers.IntegerField(required=False, allow_null=True)


class TicketUpdateSerializer(serializers.Serializer):
    contact_id = serializers.IntegerField(required=False, allow_null=True)
    subject = serializers.CharField(max_length=255, required=False)
    priority = serializers.ChoiceField(choices=TicketPriority.choices, required=False)
    assignee_id = serializers.IntegerField(required=False, allow_null=True)
    status = serializers.ChoiceField(choices=TicketStatus.choices, required=False)

    def validate(self, attrs):
        if not attrs:
            raise serializers.ValidationError("Provide at least one field to update.")
        return attrs
