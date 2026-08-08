import os

from .base import *

DEBUG = False

# --- Deployment hardening (docs/06-architecture.md §6/§7, roadmap Phase 4) ---
# `manage.py check --deploy` flags every setting below by default when
# absent. Values here are production-sensible defaults, overridable via
# env vars for unusual deployment topologies.

# Refuse to boot with Django's auto-generated dev key — better a loud
# startup failure than a silently insecure production deployment.
if not SECRET_KEY or SECRET_KEY.startswith("django-insecure-"):
    raise RuntimeError(
        "DJANGO_SECRET_KEY must be set to a real, unique, random value in "
        "production (see .env.example) — refusing to start with the "
        "insecure default."
    )


SECURE_SSL_REDIRECT = os.environ.get("SECURE_SSL_REDIRECT", "True") == "True"
SESSION_COOKIE_SECURE = os.environ.get("SESSION_COOKIE_SECURE", "True") == "True"
CSRF_COOKIE_SECURE = os.environ.get("CSRF_COOKIE_SECURE", "True") == "True"
SECURE_HSTS_SECONDS = int(os.environ.get("SECURE_HSTS_SECONDS", 60 * 60 * 24 * 30))  # 30 days
SECURE_HSTS_INCLUDE_SUBDOMAINS = os.environ.get("SECURE_HSTS_INCLUDE_SUBDOMAINS", "True") == "True"
SECURE_HSTS_PRELOAD = os.environ.get("SECURE_HSTS_PRELOAD", "True") == "True"

# If TLS terminates at an upstream load balancer/reverse proxy rather
# than at Django itself, that proxy must forward this header so Django
# knows the original request was HTTPS — otherwise SECURE_SSL_REDIRECT
# redirect-loops. Only enable this if your proxy is configured to set
# (and strip any client-supplied copy of) this header.
if os.environ.get("BEHIND_TLS_TERMINATING_PROXY", "True") == "True":
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

if not ALLOWED_HOSTS:
    raise RuntimeError(
        "ALLOWED_HOSTS must be set in production (comma-separated, e.g. "
        "ALLOWED_HOSTS=api.example.com in .env) — refusing to start with "
        "an empty allowlist."
    )
