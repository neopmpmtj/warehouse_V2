from django.shortcuts import render
from django.views.decorators.http import require_GET

from accounts.capabilities import inventory_permission_flags

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
