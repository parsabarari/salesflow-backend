from rest_framework import serializers
from rest_framework_simplejwt.exceptions import InvalidToken
from rest_framework_simplejwt.serializers import TokenRefreshSerializer, TokenObtainPairSerializer

from apps.accounts.services import TokenBlocklistService
from apps.accounts.tokens import RefreshToken
from apps.accounts.models import User



class CustomTokenRefreshSerializer(TokenRefreshSerializer):
    token_class = RefreshToken

    def validate(self, attrs):
        refresh = self.token_class(attrs["refresh"])
        if TokenBlocklistService.is_blocklisted(str(refresh["jti"])):
            raise InvalidToken(
                {"detail": "Token is blocklisted.", "code": "token_not_valid"}
            )
        return super().validate(attrs)    


class SignupSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, min_length=8)
    organization_name = serializers.CharField(max_length=255)

    def validate_email(self, value):
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return value


class LogoutSerializer(serializers.Serializer):
    refresh = serializers.CharField()


class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()


class PasswordResetConfirmSerializer(serializers.Serializer):
    uid = serializers.CharField()
    token = serializers.CharField()
    new_password = serializers.CharField(write_only=True, min_length=8)


class EmailVerifySerializer(serializers.Serializer):
    uid = serializers.CharField()
    token = serializers.CharField()


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    token_class = RefreshToken
