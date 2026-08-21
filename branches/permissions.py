from functools import wraps

from django.contrib.auth.views import redirect_to_login
from django.http import HttpResponseForbidden, JsonResponse

from accounts.authz import deny_if_inactive

from .capabilities import is_branch_member


def branch_required(view_func):
    """Gate /branch/* pages: any active user with at least one branch membership."""

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
        if not is_branch_member(request.user):
            if wants_json:
                return JsonResponse({"error": "Branch membership required"}, status=403)
            return HttpResponseForbidden("Branch membership required")
        return view_func(request, *args, **kwargs)

    return wrapped
