from django.shortcuts import render
from django.views.decorators.http import require_GET

from accounts.capabilities import inventory_permission_flags
from branches.capabilities import can_adjust_branch_stock, can_approve_request
from branches.permissions import active_branch_required

from .permissions import inventory_required


@inventory_required
@require_GET
def goods_receipt_console(request):
    flags = inventory_permission_flags(request.user)
    return render(
        request,
        "inventory/goods_receipts.html",
        {
            "can_add_goodsreceipt": flags["add_goodsreceipt"],
            "can_adjust_stock": flags["can_adjust_stock"],
        },
    )


@active_branch_required
@require_GET
def branch_receipt_console(request):
    branch = request.active_branch
    return render(
        request,
        "inventory/branch_receipts.html",
        {
            "branch": branch,
            "can_short_close": can_approve_request(request.user, branch),
            "can_adjust": can_adjust_branch_stock(request.user, branch),
        },
    )
