from rest_framework_simplejwt.exceptions import InvalidToken
from rest_framework_simplejwt.serializers import TokenRefreshSerializer

from apps.accounts.services import TokenBlocklistService
from apps.accounts.tokens import RefreshToken


class CustomTokenRefreshSerializer(TokenRefreshSerializer):
    token_class = RefreshToken

    def validate(self, attrs):
        refresh = self.token_class(attrs["refresh"])
        if TokenBlocklistService.is_blocklisted(str(refresh["jti"])):
            raise InvalidToken(
                {"detail": "Token is blocklisted.", "code": "token_not_valid"}
            )
        return super().validate(attrs)
