import time

from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.views import TokenObtainPairView

from apps.accounts.services import (TokenBlocklistService, EmailVerificationService,
                                    PasswordResetService, )
from apps.accounts.serializers import (
    CustomTokenObtainPairSerializer,
    EmailVerifySerializer,
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    SignupSerializer,
)
from apps.accounts.tokens import RefreshToken
from apps.organizations.services import SignupService


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


class LoginView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer
    permission_classes = [AllowAny]


class SignupView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = SignupSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user, organization, membership = SignupService.signup(**serializer.validated_data)
        return Response(
            {
                "user_id": user.id,
                "email": user.email,
                "organization_id": organization.id,
                "organization_name": organization.name,
                "role": membership.role,
            },
            status=status.HTTP_201_CREATED,
        )


class EmailVerifyView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = EmailVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        ok = EmailVerificationService.verify(**serializer.validated_data)
        if not ok:
            return Response({"detail": "Invalid or expired token."}, status=status.HTTP_400_BAD_REQUEST)
        return Response(status=status.HTTP_200_OK)


class PasswordResetRequestView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = PasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        PasswordResetService.request(**serializer.validated_data)
        # همیشه ۲۰۰ برمی‌گردانیم، صرف‌نظر از وجود/عدم‌وجود ایمیل
        return Response(status=status.HTTP_200_OK)


class PasswordResetConfirmView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        ok = PasswordResetService.confirm(**serializer.validated_data)
        if not ok:
            return Response({"detail": "Invalid or expired token."}, status=status.HTTP_400_BAD_REQUEST)
        return Response(status=status.HTTP_200_OK)
