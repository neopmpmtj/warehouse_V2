from functools import wraps

from django.contrib.auth.views import redirect_to_login
from django.http import HttpResponseForbidden, JsonResponse

from accounts.authz import deny_if_inactive

from .capabilities import is_warehouse_staff


def warehouse_threads_required(view_func):
    """Warehouse-side gate for /manage/threads/ (capability-based).

    Not a Django-perm check: the ``threads`` app has no group permissions by
    design (see ``capabilities.py``). Requires an active warehouse-group user.
    """

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
        if not is_warehouse_staff(request.user):
            if wants_json:
                return JsonResponse(
                    {"error": "Warehouse access required"},
                    status=403,
                )
            return HttpResponseForbidden("Warehouse access required")
        return view_func(request, *args, **kwargs)

    return wrapped
