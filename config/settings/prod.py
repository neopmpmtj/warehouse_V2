"""Production settings — VPS / DigitalOcean (strict security).

Requires these in .env on the server:
    DJANGO_SECRET_KEY, ALLOWED_HOSTS, DATABASE_URL
"""

from decouple import Csv, config

from .base import *  # noqa: F401, F403

DEBUG = False

# Accept both env names; .env.example and DEPLOYMENT.md historically used
# SECRET_KEY, prod.py used DJANGO_SECRET_KEY. Read DJANGO_SECRET_KEY first,
# fall back to SECRET_KEY. Empty (both unset) fails fast at startup.
SECRET_KEY = config("DJANGO_SECRET_KEY", default=config("SECRET_KEY", default=""))

ALLOWED_HOSTS = config("ALLOWED_HOSTS", cast=Csv())

# Security (strict for production)
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"

# Reverse proxy (nginx in front)
USE_X_FORWARDED_HOST = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

CSRF_TRUSTED_ORIGINS = config("CSRF_TRUSTED_ORIGINS", cast=Csv(), default="")
