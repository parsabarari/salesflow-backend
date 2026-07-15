from django.contrib import admin
from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
from drf_spectacular.views import (SpectacularAPIView,SpectacularSwaggerView,
                                   SpectacularRedocView,)

from apps.accounts.views import LogoutView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/auth/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("api/v1/auth/logout/", LogoutView.as_view(), name="logout"),


    path("api/schema/",SpectacularAPIView.as_view(),name="schema",),
    path("api/schema/swagger/",SpectacularSwaggerView.as_view(url_name="schema"),name="swagger-ui",),
    path("api/schema/redoc/",SpectacularRedocView.as_view(url_name="schema"),name="redoc",),
]
