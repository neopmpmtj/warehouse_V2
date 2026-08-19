from django.shortcuts import render
from django.views.decorators.http import require_GET

from .permissions import catalog_required


@catalog_required
@require_GET
def staff_dashboard(request):
    return render(
        request,
        "products/dashboard.html",
        {
            "groups": list(
                request.user.groups.order_by("name").values_list("name", flat=True)
            ),
            "permissions": sorted(request.user.get_all_permissions()),
        },
    )
