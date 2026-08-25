from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.views.decorators.cache import cache_control
from django.views.decorators.http import require_GET

from .navigation import branch_dashboard_cards, branch_page_context
from .permissions import active_branch_required
from .services import BRANCH_HOME_URL, get_active_memberships, set_active_branch


@login_required
def branch_select(request):
    """Picker: 0 -> message, 1 -> auto-select, N -> choose (lock 5 / plan §7)."""
    memberships = list(get_active_memberships(request.user))

    if request.method == "POST":
        branch_id = request.POST.get("branch_id")
        selected = next(
            (m.branch for m in memberships if str(m.branch_id) == str(branch_id)),
            None,
        )
        if selected is not None:
            set_active_branch(request, selected)
            return redirect(BRANCH_HOME_URL)

    if len(memberships) == 1:
        set_active_branch(request, memberships[0].branch)
        return redirect(BRANCH_HOME_URL)

    return render(request, "branches/select.html", {"memberships": memberships})


@active_branch_required
@require_GET
def branch_dashboard(request):
    memberships = list(get_active_memberships(request.user))
    context = branch_page_context(request)
    context["cards"] = branch_dashboard_cards(include_picker=len(memberships) > 1)
    return render(request, "branches/dashboard.html", context)


@active_branch_required
@require_GET
def branch_catalog(request):
    context = branch_page_context(request)
    context.update(
        {
            "page_title": "Catalog",
            "page_title_key": "navBranchCatalog",
            "active_nav": "catalog",
        }
    )
    return render(request, "branches/catalog.html", context)


@cache_control(max_age=0, no_cache=True, no_store=True, must_revalidate=True)
@require_GET
def service_worker(request):
    return render(
        request,
        "branches/service_worker.js",
        content_type="application/javascript",
    )
