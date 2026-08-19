from functools import wraps

from django.contrib.auth.views import redirect_to_login
from django.http import HttpResponseForbidden, JsonResponse


def can_manage_catalog(user):
    return user.is_authenticated and user.is_staff


def staff_required(view_func):
    @wraps(view_func)
    def wrapped(request, *args, **kwargs):
        wants_json = request.path.startswith("/api/")
        if not request.user.is_authenticated:
            if wants_json:
                return JsonResponse({"error": "Authentication required"}, status=401)
            return redirect_to_login(request.get_full_path())
        if not can_manage_catalog(request.user):
            if wants_json:
                return JsonResponse({"error": "Staff access required"}, status=403)
            return HttpResponseForbidden("Staff access required")
        return view_func(request, *args, **kwargs)

    return wrapped
