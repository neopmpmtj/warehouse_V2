from django.shortcuts import render
from django.views.decorators.http import require_GET

from branches.capabilities import branch_role
from branches.navigation import branch_page_context
from branches.permissions import active_branch_required

from .permissions import warehouse_threads_required


@active_branch_required
@require_GET
def branch_thread_console(request):
    branch = request.active_branch
    context = branch_page_context(request)
    context.update(
        {
            "role": branch_role(request.user, branch),
            "page_title": "Request threads",
            "page_title_key": "title",
            "active_nav": "threads",
        }
    )
    return render(request, "threads/branch_threads.html", context)


@warehouse_threads_required
@require_GET
def warehouse_thread_console(request):
    return render(
        request,
        "threads/warehouse_threads.html",
        {},
    )
