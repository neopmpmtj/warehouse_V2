from django.shortcuts import render
from django.views.decorators.http import require_GET

from accounts.capabilities import can_edit_approval_policy, inventory_permission_flags
from branches.capabilities import branch_role, can_approve_request
from branches.permissions import active_branch_required

from .permissions import internal_request_queue_required


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


@internal_request_queue_required
@require_GET
def internal_request_queue_console(request):
    flags = inventory_permission_flags(request.user)
    return render(
        request,
        "orders/internal_requests.html",
        {
            "can_issue": flags["can_issue_goods"],
            "can_short_close": flags["can_short_close"],
        },
    )


@internal_request_queue_required
@require_GET
def branch_approval_limit_console(request):
    return render(
        request,
        "orders/branch_approval_limits.html",
        {"can_edit_approval_policy": can_edit_approval_policy(request.user)},
    )
