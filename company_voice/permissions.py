from functools import wraps

from django.contrib.auth.views import redirect_to_login
from django.http import JsonResponse

from accounts.authz import deny_if_inactive


def login_required_active(view_func):
    """Any authenticated, active user may access Company Voice."""

    @wraps(view_func)
    def wrapped(request, *args, **kwargs):
        wants_json = request.path.startswith("/api/")
        inactive = deny_if_inactive(request)
        if inactive is not None:
            return inactive
        if not request.user.is_authenticated:
            if wants_json:
                return JsonResponse({"error": "Authentication required"}, status=401)
            return redirect_to_login(request.get_full_path())
        return view_func(request, *args, **kwargs)

    return wrapped
