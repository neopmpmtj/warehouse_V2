from django.shortcuts import render
from django.views.decorators.http import require_GET

from .permissions import inventory_required


@inventory_required
@require_GET
def goods_receipt_console(request):
    return render(request, "inventory/goods_receipts.html")
