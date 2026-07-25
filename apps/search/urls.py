from django.urls import path

from apps.search.views import GlobalSearchView

urlpatterns = [
    path("<int:organization_id>/search/", GlobalSearchView.as_view(), name="global-search"),
]
