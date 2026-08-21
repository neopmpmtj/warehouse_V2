from django.urls import path

from . import views

urlpatterns = [
    path(
        "manage/internal-requests/",
        views.internal_request_queue_console,
        name="internal_request_queue_console",
    ),
    path(
        "manage/branch-approval-limits/",
        views.branch_approval_limit_console,
        name="branch_approval_limit_console",
    ),
]
