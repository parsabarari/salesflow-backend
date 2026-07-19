from django.http import HttpResponse
from django.urls import path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
def scalar_viewer(request):
    openapi_url = "/api/schema/"
    title = "Scalar Api Reference"
    scalar_js_url = "https://cdn.jsdelivr.net/npm/@scalar/api-reference"
    scalar_proxy_url = ""
    scalar_favicon_url = "/static/favicon.ico"
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>{title}</title>
        <meta charset="utf-8"/>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <link rel="shortcut icon" href="{scalar_favicon_url}">
        <style>
        body {{
            margin: 0;
            padding: 0;
        }}
        </style>
    </head>
    <body>
        <noscript>
            Scalar requires Javascript to function. Please enable it to browse the documentation.
        </noscript>
        <script
            id="api-reference"
            data-url="{openapi_url}"
            data-proxy-url="{scalar_proxy_url}"
            >
        </script>
        <script src="{scalar_js_url}"></script>
    </body>
    </html>
    """
    return HttpResponse(html)
urlpatterns_scalar = [
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", scalar_viewer, name="docs"),
]