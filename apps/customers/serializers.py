from rest_framework import serializers

from apps.customers.models import Contact, Customer


class ContactSerializer(serializers.ModelSerializer):
    class Meta:
        model = Contact
        fields = ["id", "customer", "name", "email", "phone", "created_at"]
        validators = []


class ContactCreateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255)
    email = serializers.EmailField(required=False, allow_null=True)
    phone = serializers.CharField(max_length=30, required=False, allow_null=True)


class CustomerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Customer
        fields = ["id", "type", "name", "email", "phone", "created_at"]
        read_only_fields = ["type", "created_at"]  # type change isn't specified anywhere — treat as immutable
        validators = []


class CustomerUpdateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255, required=False)
    email = serializers.EmailField(required=False, allow_null=True)
    phone = serializers.CharField(max_length=30, required=False, allow_null=True)

    def validate(self, attrs):
        if not attrs:
            raise serializers.ValidationError("Provide at least one field to update.")
        return attrs
