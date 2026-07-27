import os
from datetime import timedelta
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent

SECRET_KEY = os.environ.get(
    "DJANGO_SECRET_KEY",
    "django-insecure-salesflow-local-development-key",
)

DEBUG = False

ALLOWED_HOSTS = os.environ.get("DJANGO_ALLOWED_HOSTS", "").split()

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.postgres",
    "django.contrib.staticfiles",
    "rest_framework",
    "rest_framework_simplejwt",
    "apps.core",
    "apps.accounts",
    "apps.organizations",
    "apps.audit",
    "apps.leads",
    "apps.customers",
    "apps.activities",
    "apps.tickets",
    "apps.collaboration",
    "apps.notifications",
    "apps.dashboard",
    "apps.search",
    "drf_spectacular",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "apps.core.middleware.AdminOrgBypassMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

STATIC_URL = "static/"

STATICFILES_DIRS = [
    BASE_DIR / "static",
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ.get("POSTGRES_DB", "salesflow"),
        "USER": os.environ.get("POSTGRES_USER", "postgres"),
        "PASSWORD": os.environ.get("POSTGRES_PASSWORD", ""),
        "HOST": os.environ.get("POSTGRES_HOST", "localhost"),
        "PORT": os.environ.get("POSTGRES_PORT", "5432"),
    }
}

AUTH_USER_MODEL = "accounts.User"

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

JWT_ACCESS_TOKEN_LIFETIME_MINUTES = int(
    os.environ.get("JWT_ACCESS_TOKEN_LIFETIME_MINUTES", 15)
)
JWT_REFRESH_TOKEN_LIFETIME_DAYS = int(
    os.environ.get("JWT_REFRESH_TOKEN_LIFETIME_DAYS", 7)
)

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ],

    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=JWT_ACCESS_TOKEN_LIFETIME_MINUTES),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=JWT_REFRESH_TOKEN_LIFETIME_DAYS),
    "ROTATE_REFRESH_TOKENS": False,
    "BLACKLIST_AFTER_ROTATION": False,
    "AUTH_HEADER_TYPES": ("Bearer",),
    "USER_ID_FIELD": "id",
    "USER_ID_CLAIM": "user_id",
    "REFRESH_TOKEN_CLASS": "apps.accounts.tokens.RefreshToken",
    "TOKEN_REFRESH_SERIALIZER": "apps.accounts.serializers.CustomTokenRefreshSerializer",
    "TOKEN_OBTAIN_SERIALIZER": "apps.accounts.serializers.CustomTokenObtainPairSerializer",
}

# drf_spectacular
SPECTACULAR_SETTINGS = {
    "TITLE": "SalesFlow CRM API",
    "DESCRIPTION": "Multi-tenant CRM SaaS backend — internal API consumed by a separately-developed frontend.",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "SORT_OPERATIONS": False,
    "TAGS": [
        {"name": "Auth", "description": "Signup, login, logout, token refresh, password reset, email verification."},
        {"name": "Organizations & Members", "description": "Organization settings, memberships, invitations."},
        {"name": "Leads", "description": "Lead CRUD, pipeline stage transitions, tags, timeline."},
        {"name": "Customers & Contacts", "description": "Customer and Contact CRUD, Won-lead linking resolution."},
        {"name": "Activities", "description": "Calls, meetings, tasks, reminders tied to a Lead or Customer."},
        {"name": "Tickets", "description": "Lightweight customer support ticketing."},
        {"name": "Collaboration", "description": "Comments, @mentions, file attachments."},
        {"name": "Notifications", "description": "In-app notification feed."},
        {"name": "Dashboard", "description": "Aggregated summary metrics."},
        {"name": "Search", "description": "Global RBAC-scoped search across Leads, Customers, Tickets."},
        {"name": "Audit Log", "description": "Owner/Admin-only administrative action log."},
    ],
}


FRONTEND_BASE_URL = os.environ.get("FRONTEND_BASE_URL", default="http://localhost:3000")



# --- Object storage (docs/06-architecture.md §2) ---
STORAGES = {
    "default": {
        "BACKEND": "storages.backends.s3.S3Storage",
    },
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
    },
}

AWS_ACCESS_KEY_ID = os.environ.get("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.environ.get("AWS_SECRET_ACCESS_KEY")
AWS_STORAGE_BUCKET_NAME = os.environ.get("AWS_STORAGE_BUCKET_NAME")
AWS_S3_ENDPOINT_URL = os.environ.get("AWS_S3_ENDPOINT_URL")
AWS_S3_REGION_NAME = os.environ.get("AWS_S3_REGION_NAME", "us-east-1")

# MinIO doesn't support virtual-hosted-style bucket addressing
# (bucket-name.your-endpoint.com) the way real AWS S3 does — it needs
# path-style (your-endpoint.com/bucket-name) instead.
AWS_S3_ADDRESSING_STYLE = "path"

# Attachments are private business data, not public assets — every
# read goes through a short-lived signed URL (API Spec §10), never a
# permanently-public object URL.
AWS_DEFAULT_ACL = None
AWS_QUERYSTRING_AUTH = True
AWS_QUERYSTRING_EXPIRE = 3600  # signed URL lifetime, seconds (1 hour)

# Two uploads with the same filename must not silently overwrite each
# other — each Attachment.file_reference should point at exactly the
# bytes that were uploaded for it.
AWS_S3_FILE_OVERWRITE = False
