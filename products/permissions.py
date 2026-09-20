from functools import wraps

from django.contrib.auth.views import redirect_to_login
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import render

from accounts.authz import deny_if_inactive, user_is_active
from accounts.capabilities import catalog_permission_flags, has_effective_perm
from accounts.groups import VIEW_ITEM

CATALOGUE_FORBIDDEN_MESSAGE = "Catalogue view permission required"


def can_view_catalog(user):
    if not user_is_active(user):
        return False
    return user.has_perm(VIEW_ITEM)


def catalog_permissions(user):
    return catalog_permission_flags(user)


def deny_unless(request, perm):
    if has_effective_perm(request.user, perm):
        return None
    message = f"Missing permission: {perm}"
    if request.path.startswith("/api/"):
        return JsonResponse({"error": message}, status=403)
    return HttpResponseForbidden(message)


def catalogue_forbidden(request):
    """HTML 403 for warehouse catalogue pages: home link + Sign out."""
    from branches.services import home_url_for_request

    return render(
        request,
        "products/catalogue_forbidden.html",
        {
            "home_url": home_url_for_request(request),
            "error_code": CATALOGUE_FORBIDDEN_MESSAGE,
        },
        status=403,
    )


def catalog_required(view_func):
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
        if not can_view_catalog(request.user):
            if wants_json:
                return JsonResponse(
                    {"error": CATALOGUE_FORBIDDEN_MESSAGE},
                    status=403,
                )
            return catalogue_forbidden(request)
        return view_func(request, *args, **kwargs)

    return wrapped
