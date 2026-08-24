"""Test settings: fast hasher + quiet logging (used automatically by manage.py test)."""

from .dev import *  # noqa: F401, F403

TESTING = True

# PBKDF2 (~870k iterations) dominates test time; use a fast hasher under test.
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
