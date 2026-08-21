from django.shortcuts import render
from django.views.decorators.http import require_GET

from branches.capabilities import branch_role, can_approve_request
from branches.permissions import active_branch_required


@active_branch_required
@require_GET
def request_console(request):
    branch = request.active_branch
    return render(
        request,
        "orders/requests.html",
        {
            "branch": branch,
            "role": branch_role(request.user, branch),
            "can_approve": can_approve_request(request.user, branch),
        },
    )
