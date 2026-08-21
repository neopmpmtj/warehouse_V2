from functools import wraps

from django.contrib.auth.views import redirect_to_login
from django.http import HttpResponseForbidden, JsonResponse

from accounts.authz import deny_if_inactive, user_is_active
from accounts.capabilities import has_effective_perm

VIEW_INTERNAL_REQUEST = "orders.view_internalrequest"
ISSUE_GOODS = "inventory.can_issue_goods"


def can_view_internal_requests(user):
    if not user_is_active(user):
        return False
    return user.has_perm(VIEW_INTERNAL_REQUEST)


def deny_unless(request, perm):
    if has_effective_perm(request.user, perm):
        return None
    message = f"Missing permission: {perm}"
    if request.path.startswith("/api/"):
        return JsonResponse({"error": message}, status=403)
    return HttpResponseForbidden(message)


def internal_request_queue_required(view_func):
    """Warehouse-side gate for the request queue (/manage/internal-requests/)."""

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
        if not can_view_internal_requests(request.user):
            if wants_json:
                return JsonResponse(
                    {"error": "Internal request view permission required"},
                    status=403,
                )
            return HttpResponseForbidden("Internal request view permission required")
        return view_func(request, *args, **kwargs)

    return wrapped
