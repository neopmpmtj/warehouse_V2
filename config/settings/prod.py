"""Production settings — VPS / DigitalOcean (strict security).

Requires these in .env on the server:
    DJANGO_SECRET_KEY, ALLOWED_HOSTS, DATABASE_URL
Set SECURE_SSL_REDIRECT=True only after TLS (certbot) is serving 443.
"""

from django.core.exceptions import ImproperlyConfigured
from decouple import Csv, config

from .base import *  # noqa: F401, F403

DEBUG = False

if not config("DATABASE_URL", default=""):
    raise ImproperlyConfigured("DATABASE_URL is required in production.")

# DJANGO_SECRET_KEY first; fall back to legacy SECRET_KEY.
# Missing both: decouple raises. Empty string: Django ImproperlyConfigured at WSGI load.
SECRET_KEY = config("DJANGO_SECRET_KEY", default="") or config("SECRET_KEY")

ALLOWED_HOSTS = config("ALLOWED_HOSTS", cast=Csv())

# Default False so gunicorn can start on HTTP until certbot enables 443.
SECURE_SSL_REDIRECT = config("SECURE_SSL_REDIRECT", default=False, cast=bool)
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 31536000 if SECURE_SSL_REDIRECT else 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = bool(SECURE_SSL_REDIRECT)
SECURE_HSTS_PRELOAD = False
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"

# Reverse proxy (nginx in front). Host comes from nginx `Host $host`;
# do not honour client X-Forwarded-Host.
USE_X_FORWARDED_HOST = False
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

CSRF_TRUSTED_ORIGINS = config("CSRF_TRUSTED_ORIGINS", cast=Csv(), default="")

if GOOGLE_CLIENT_ID and "localhost" in (GOOGLE_OAUTH_REDIRECT_URI or ""):
    raise ImproperlyConfigured(
        "GOOGLE_OAUTH_REDIRECT_URI must be the public HTTPS callback in production."
    )
