from django.contrib import admin
from django.urls import path, include
from drf_spectacular.views import (SpectacularAPIView,SpectacularSwaggerView,
                                   SpectacularRedocView,)


urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/auth/", include("apps.accounts.urls")),
    path("api/v1/organizations/", include("apps.organizations.urls")),
    path("api/v1/organizations/", include("apps.leads.urls")),


    path("api/schema/",SpectacularAPIView.as_view(),name="schema",),
    path("api/schema/swagger/",SpectacularSwaggerView.as_view(url_name="schema"),name="swagger-ui",),
    path("api/schema/redoc/",SpectacularRedocView.as_view(url_name="schema"),name="redoc",),
]
