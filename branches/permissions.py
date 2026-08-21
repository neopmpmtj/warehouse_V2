from functools import wraps

from django.contrib.auth.views import redirect_to_login
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import redirect

from accounts.authz import deny_if_inactive

from .capabilities import is_branch_member


def _resolve_branch_gate(request, wants_json):
    """Return a blocking response for an unauthorized request, else None."""
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
    return None


def active_branch_required(view_func):
    """Gate branch work pages: branch member + a selected active branch."""

    @wraps(view_func)
    def wrapped(request, *args, **kwargs):
        wants_json = request.path.startswith("/api/")
        gate = _resolve_branch_gate(request, wants_json)
        if gate is not None:
            return gate
        if request.active_branch is None:
            if wants_json:
                return JsonResponse({"error": "No active branch selected"}, status=403)
            return redirect("branch_select")
        return view_func(request, *args, **kwargs)

    return wrapped
