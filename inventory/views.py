from django.shortcuts import render
from django.views.decorators.http import require_GET

from accounts.capabilities import inventory_permission_flags, procurement_permission_flags
from branches.capabilities import can_adjust_branch_stock, can_approve_request
from branches.navigation import branch_page_context
from branches.permissions import active_branch_required

from .permissions import branch_alerts_required, inventory_required, warehouse_alerts_required


@inventory_required
@require_GET
def goods_receipt_console(request):
    flags = inventory_permission_flags(request.user)
    po_flags = procurement_permission_flags(request.user)
    return render(
        request,
        "inventory/goods_receipts.html",
        {
            "can_add_goodsreceipt": flags["add_goodsreceipt"],
            "can_adjust_stock": flags["can_adjust_stock"],
            "can_change_purchaseorder": po_flags["change_purchaseorder"],
        },
    )


@active_branch_required
@require_GET
def branch_receipt_console(request):
    branch = request.active_branch
    context = branch_page_context(request)
    context.update(
        {
            "can_short_close": can_approve_request(request.user, branch),
            "can_adjust": can_adjust_branch_stock(request.user, branch),
            "page_title": "Receipts",
            "page_title_key": "navBranchReceipts",
            "active_nav": "receipts",
        }
    )
    return render(request, "inventory/branch_receipts.html", context)


@warehouse_alerts_required
@require_GET
def warehouse_alerts_console(request):
    return render(
        request,
        "inventory/warehouse_alerts.html",
        {"side": "warehouse"},
    )


@active_branch_required
@branch_alerts_required
@require_GET
def branch_alerts_console(request):
    context = branch_page_context(request)
    context.update(
        {
            "page_title": "Alerts",
            "page_title_key": "cardAlerts",
            "active_nav": "",
            "side": "branch",
        }
    )
    return render(request, "inventory/branch_alerts.html", context)



@inventory_required
@require_GET
def goods_receipt_console(request):
    flags = inventory_permission_flags(request.user)
    po_flags = procurement_permission_flags(request.user)
    return render(
        request,
        "inventory/goods_receipts.html",
        {
            "can_add_goodsreceipt": flags["add_goodsreceipt"],
            "can_adjust_stock": flags["can_adjust_stock"],
            "can_change_purchaseorder": po_flags["change_purchaseorder"],
        },
    )


@active_branch_required
@require_GET
def branch_receipt_console(request):
    branch = request.active_branch
    context = branch_page_context(request)
    context.update(
        {
            "can_short_close": can_approve_request(request.user, branch),
            "can_adjust": can_adjust_branch_stock(request.user, branch),
            "page_title": "Receipts",
            "page_title_key": "navBranchReceipts",
            "active_nav": "receipts",
        }
    )
    return render(request, "inventory/branch_receipts.html", context)
