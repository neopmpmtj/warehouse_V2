from functools import wraps

from django.contrib.auth.views import redirect_to_login
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import render

from accounts.authz import deny_if_inactive, user_is_active
from accounts.capabilities import can_approve_purchase_order, has_effective_perm
from branches.capabilities import can_approve_request

VIEW_GOODS_RECEIPT = "inventory.view_goodsreceipt"
ADD_GOODS_RECEIPT = "inventory.add_goodsreceipt"
ADJUST_STOCK = "inventory.can_adjust_stock"
ALERTS_FORBIDDEN_MESSAGE = "Alerts view permission required"


def can_view_inventory(user):
    if not user_is_active(user):
        return False
    return user.has_perm(VIEW_GOODS_RECEIPT)


def deny_unless(request, perm):
    if has_effective_perm(request.user, perm):
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


def alerts_forbidden(request):
    from branches.services import home_url_for_request

    return render(
        request,
        "inventory/alerts_forbidden.html",
        {
            "home_url": home_url_for_request(request),
            "error_code": ALERTS_FORBIDDEN_MESSAGE,
        },
        status=403,
    )


def warehouse_alerts_required(view_func):
    """Warehouse manager alerts: admin, or manager grade 2+."""

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
        if not can_approve_purchase_order(request.user):
            if wants_json:
                return JsonResponse({"error": ALERTS_FORBIDDEN_MESSAGE}, status=403)
            return alerts_forbidden(request)
        return view_func(request, *args, **kwargs)

    return wrapped


def branch_alerts_required(view_func):
    """Branch manager alerts: manager or admin on the active branch."""

    @wraps(view_func)
    def wrapped(request, *args, **kwargs):
        wants_json = request.path.startswith("/api/")
        if not can_approve_request(request.user, getattr(request, "active_branch", None)):
            if wants_json:
                return JsonResponse({"error": ALERTS_FORBIDDEN_MESSAGE}, status=403)
            return alerts_forbidden(request)
        return view_func(request, *args, **kwargs)

    return wrapped
