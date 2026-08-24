from django.shortcuts import render
from django.views.decorators.http import require_GET

from branches.capabilities import branch_role
from branches.permissions import active_branch_required

from .permissions import warehouse_threads_required


@active_branch_required
@require_GET
def branch_thread_console(request):
    branch = request.active_branch
    return render(
        request,
        "threads/branch_threads.html",
        {
            "branch": branch,
            "role": branch_role(request.user, branch),
        },
    )


@warehouse_threads_required
@require_GET
def warehouse_thread_console(request):
    return render(
        request,
        "threads/warehouse_threads.html",
        {},
    )
