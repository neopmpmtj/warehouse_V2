from django.shortcuts import render
from django.views.decorators.http import require_GET

from .permissions import procurement_required


@procurement_required
@require_GET
def purchase_order_console(request):
    return render(request, "procurement/purchase_orders.html")
