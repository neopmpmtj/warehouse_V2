"""Development settings — local machine defaults (relaxed security)."""

from decouple import Csv, config

from .base import *  # noqa: F401, F403

DEBUG = True

SECRET_KEY = config(
    "DJANGO_SECRET_KEY",
    default="django-insecure-dev-only-5c1f8f8f4f4f4f4f4f4f4f4f4f4f4f4f",
)

ALLOWED_HOSTS = config("ALLOWED_HOSTS", cast=Csv(), default="localhost,127.0.0.1")

# Security (relaxed for development)
SECURE_SSL_REDIRECT = False
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
SECURE_HSTS_SECONDS = 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = False
SECURE_HSTS_PRELOAD = False
