from functools import wraps

from django.contrib.auth.views import redirect_to_login
from django.http import HttpResponseForbidden, JsonResponse

from accounts.authz import deny_if_inactive, user_is_active
from accounts.groups import (
    ADD_FAMILY,
    ADD_ITEM,
    ADD_SUPPLIER,
    ADD_SUPPLIER_ITEM_PRICE,
    CHANGE_FAMILY,
    CHANGE_ITEM,
    CHANGE_SUPPLIER,
    CHANGE_SUPPLIER_ITEM_PRICE,
    VIEW_ITEM,
)


def can_view_catalog(user):
    if not user_is_active(user):
        return False
    return user.has_perm(VIEW_ITEM)


def catalog_permissions(user):
    return {
        "add_item": user.has_perm(ADD_ITEM),
        "change_item": user.has_perm(CHANGE_ITEM),
        "add_family": user.has_perm(ADD_FAMILY),
        "change_family": user.has_perm(CHANGE_FAMILY),
        "add_supplier": user.has_perm(ADD_SUPPLIER),
        "change_supplier": user.has_perm(CHANGE_SUPPLIER),
        "add_supplier_item_price": user.has_perm(ADD_SUPPLIER_ITEM_PRICE),
        "change_supplier_item_price": user.has_perm(CHANGE_SUPPLIER_ITEM_PRICE),
    }


def deny_unless(request, perm):
    if request.user.has_perm(perm):
        return None
    message = f"Missing permission: {perm}"
    if request.path.startswith("/api/"):
        return JsonResponse({"error": message}, status=403)
    return HttpResponseForbidden(message)


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
                    {"error": "Catalogue view permission required"},
                    status=403,
                )
            return HttpResponseForbidden("Catalogue view permission required")
        return view_func(request, *args, **kwargs)

    return wrapped
