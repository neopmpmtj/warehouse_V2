"""Shared auth helpers for console/API permission gates."""

from django.contrib.auth import SESSION_KEY, get_user_model, logout
from django.http import HttpResponseForbidden, JsonResponse


def user_is_active(user):
    return bool(
        getattr(user, "is_authenticated", False)
        and getattr(user, "pk", None)
        and getattr(user, "is_active", False)
    )


def _inactive_response(request):
    message = "Account is inactive"
    if request.path.startswith("/api/"):
        return JsonResponse({"error": message}, status=403)
    return HttpResponseForbidden(message)


def deny_if_inactive(request):
    """Block deactivated users; clear any leftover session and return 403.

    Django's auth backend already treats inactive users as AnonymousUser on the
    next request, but leaves ``_auth_user_id`` in the session. Detect that case
    (and the rare path where ``is_authenticated`` is still True) so offboarded
    accounts get a clear 403 instead of looking merely unauthenticated.
    """
    if request.user.is_authenticated:
        if request.user.is_active:
            return None
        logout(request)
        return _inactive_response(request)

    session_uid = request.session.get(SESSION_KEY)
    if not session_uid:
        return None

    User = get_user_model()
    try:
        still_active = User.objects.filter(pk=session_uid, is_active=True).exists()
    except (TypeError, ValueError):
        still_active = False

    if still_active:
        return None

    logout(request)
    return _inactive_response(request)
