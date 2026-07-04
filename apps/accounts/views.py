import time

from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError

from apps.accounts.services import TokenBlocklistService
from apps.accounts.tokens import RefreshToken


class LogoutView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        refresh_token = request.data.get("refresh")
        if not refresh_token:
            return Response(
                {"detail": "Refresh token is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            token = RefreshToken(refresh_token)
        except TokenError:
            return Response(
                {"detail": "Token is invalid or expired."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        jti = str(token["jti"])
        ttl_seconds = max(int(token["exp"] - time.time()), 0)
        TokenBlocklistService.blocklist(jti, ttl_seconds)
        return Response(status=status.HTTP_204_NO_CONTENT)
