"""DB-backed login throttling (H2 — production blocker fix).

Shared across all gunicorn workers (DB, not per-process cache).
Lockout is keyed on the attempted username; the client IP is recorded
for forensics. ``LOGIN_THROTTLE_MAX_FAILURES`` failures within
``LOGIN_THROTTLE_WINDOW_MINUTES`` lock the username until the window
passes or a successful login clears the failures.
"""

from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from .models import LoginFailure


def _window_start():
    minutes = getattr(settings, "LOGIN_THROTTLE_WINDOW_MINUTES", 15)
    return timezone.now() - timedelta(minutes=minutes)


def is_login_locked(username):
    """True when the username has too many recent failures."""
    if not username:
        return False
    max_failures = getattr(settings, "LOGIN_THROTTLE_MAX_FAILURES", 5)
    return (
        LoginFailure.objects.filter(
            username__iexact=username,
            created_at__gte=_window_start(),
        ).count()
        >= max_failures
    )


def record_failure(username, ip=""):
    """Record one failed login / link-confirm attempt."""
    if not username:
        return
    LoginFailure.objects.create(username=username, ip=ip or None)


def clear_failures(username):
    """Drop failure history after a successful login."""
    if not username:
        return
    LoginFailure.objects.filter(username__iexact=username).delete()
