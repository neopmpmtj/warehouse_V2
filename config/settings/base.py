"""
Django base settings for CentCompras (shared by dev, prod, and test).

For more information on this file, see
https://docs.djangoproject.com/en/6.1/topics/settings/

Secrets and environment-specific values live in .env (gitignored), read via
python-decouple. A DATABASE_URL connection string is the primary DB config
(dev and prod); POSTGRES_* variables remain a supported fallback for local dev.
"""

import os
import sys
from pathlib import Path

from decouple import Csv, config
import dj_database_url

BASE_DIR = Path(__file__).resolve().parent.parent.parent

# True when running under `manage.py test` — used to keep test output quiet/fast.
TESTING = "test" in sys.argv

if TESTING:
    # PBKDF2 (~870k iterations) dominates test time; use a fast hasher under test.
    PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

INSTALLED_APPS = [
    "logging_utils",
    "accounts.admin_site.CentComprasAdminConfig",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "accounts",
    "products",
    "procurement",
    "inventory",
    "branches",
    "orders",
    "threads",
    "company_voice",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "branches.middleware.ActiveBranchMiddleware",
    "accounts.middleware.UserTimezoneMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "config.context_processors.help_manual",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# Database — DATABASE_URL when set (production); POSTGRES_* env fallback keeps
# local dev working exactly as before without URL-encoding the password.
# conn_max_age=60: reuse connections per worker (M2); health checks apply
# only when conn_max_age > 0.
_database_url = config("DATABASE_URL", default=None)
if _database_url:
    DATABASES = {
        "default": dj_database_url.config(
            default=_database_url,
            conn_max_age=60,
            conn_health_checks=True,
        )
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": "centcompras_db",
            "USER": config("POSTGRES_USER", default="appuser"),
            "PASSWORD": config("POSTGRES_PASSWORD", default="your_password_here"),
            "HOST": config("POSTGRES_HOST", default="localhost"),
            "PORT": config("POSTGRES_PORT", default="5432"),
        }
    }

AUTH_USER_MODEL = "accounts.User"

LOGIN_URL = "/accounts/login/"
LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/accounts/login/"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# Login throttling (H2 — production blocker fix). DB-backed LoginFailure rows
# shared across gunicorn workers; window + threshold configurable via .env.
LOGIN_THROTTLE_MAX_FAILURES = config("LOGIN_THROTTLE_MAX_FAILURES", default=5, cast=int)
LOGIN_THROTTLE_WINDOW_MINUTES = config("LOGIN_THROTTLE_WINDOW_MINUTES", default=15, cast=int)

LANGUAGE_CODE = "en-gb"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --- Google OAuth login (login-only scopes: openid, email, profile) ---
# AUTH_MODE:
#   "both"        (default) password login + Google button (dev + initial prod)
#   "google_only" password login disabled; Google is the only method (final prod)
# GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET / GOOGLE_OAUTH_REDIRECT_URI come from
# .env — create a dedicated OAuth client in Google Cloud Console (Desktop app
# type for local dev; Web application + domain callback once deployed).
AUTH_MODE = config("AUTH_MODE", default="both")
GOOGLE_CLIENT_ID = config("GOOGLE_CLIENT_ID", default="")
GOOGLE_CLIENT_SECRET = config("GOOGLE_CLIENT_SECRET", default="")
GOOGLE_OAUTH_REDIRECT_URI = config(
    "GOOGLE_OAUTH_REDIRECT_URI",
    default="http://localhost:8000/accounts/google/callback/",
)

# Logging: see logging_utils/ — files written to logs/ (gitignored)
# Per-module: get_logger("centcompras.products"), etc.

# Google OAuth (later, production): via django-allauth — not used in dev.
# GOOGLE_OAUTH_CLIENT_ID = config("GOOGLE_OAUTH_CLIENT_ID", default="")
# GOOGLE_OAUTH_CLIENT_SECRET = config("GOOGLE_OAUTH_CLIENT_SECRET", default="")
