from django.shortcuts import render
from django.views.decorators.http import require_GET

from .permissions import staff_required


@staff_required
@require_GET
def staff_dashboard(request):
    return render(request, "products/dashboard.html")


def service_worker(request):
    return render(
        request,
        "products/service_worker.js",
        content_type="application/javascript",
    )
