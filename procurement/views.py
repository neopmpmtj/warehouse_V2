from django.shortcuts import render
from django.views.decorators.http import require_GET

from accounts.capabilities import can_edit_approval_policy, procurement_permission_flags

from .permissions import procurement_required


@procurement_required
@require_GET
def purchase_order_console(request):
    flags = procurement_permission_flags(request.user)
    return render(
        request,
        "procurement/purchase_orders.html",
        {
            "can_add_purchaseorder": flags["add_purchaseorder"],
            "can_change_purchaseorder": flags["change_purchaseorder"],
            "can_approve_purchaseorder": flags["can_approve"],
        },
    )


@procurement_required
@require_GET
def approval_limit_console(request):
    return render(
        request,
        "procurement/approval_limits.html",
        {"can_edit_approval_policy": can_edit_approval_policy(request.user)},
    )
