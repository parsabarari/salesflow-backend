from django.contrib import admin
from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from apps.accounts.views import LogoutView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/auth/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("api/v1/auth/logout/", LogoutView.as_view(), name="logout"),
]
