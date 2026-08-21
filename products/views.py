from django.conf import settings
from django.shortcuts import render
from django.views.decorators.http import require_GET

from .permissions import catalog_required


@catalog_required
@require_GET
def staff_dashboard(request):
    context = {
        "groups": list(
            request.user.groups.order_by("name").values_list("name", flat=True)
        ),
    }
    if request.user.is_superuser or settings.DEBUG:
        context["permissions"] = sorted(request.user.get_all_permissions())
    return render(request, "products/dashboard.html", context)
