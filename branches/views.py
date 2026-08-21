from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from .permissions import branch_required
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


@branch_required
def branch_catalog(request):
    """Placeholder for Slice 2. Requires an active branch in the session."""
    if request.active_branch is None:
        return redirect("branch_select")
    return render(
        request,
        "branches/catalog.html",
        {"branch": request.active_branch},
    )
