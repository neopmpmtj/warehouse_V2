from functools import wraps

from django.contrib.auth.views import redirect_to_login
from django.http import HttpResponseForbidden, JsonResponse

from accounts.authz import deny_if_inactive, user_is_active

VIEW_GOODS_RECEIPT = "inventory.view_goodsreceipt"
ADD_GOODS_RECEIPT = "inventory.add_goodsreceipt"
CHANGE_GOODS_RECEIPT = "inventory.change_goodsreceipt"
ADJUST_STOCK = "inventory.can_adjust_stock"


def can_view_inventory(user):
    if not user_is_active(user):
        return False
    return user.has_perm(VIEW_GOODS_RECEIPT)


def deny_unless(request, perm):
    if request.user.has_perm(perm):
        return None
    message = f"Missing permission: {perm}"
    if request.path.startswith("/api/"):
        return JsonResponse({"error": message}, status=403)
    return HttpResponseForbidden(message)


def inventory_required(view_func):
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
        if not can_view_inventory(request.user):
            if wants_json:
                return JsonResponse(
                    {"error": "Inventory view permission required"},
                    status=403,
                )
            return HttpResponseForbidden("Inventory view permission required")
        return view_func(request, *args, **kwargs)

    return wrapped
