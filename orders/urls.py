from django.urls import path

from . import console_views

urlpatterns = [
    path("branch/requests/", console_views.request_list, name="request_list"),
    path("branch/requests/create/", console_views.request_create, name="request_create"),
    path("branch/requests/<int:request_id>/", console_views.request_detail, name="request_detail"),
    path("branch/requests/<int:request_id>/update/", console_views.request_update, name="request_update"),
    path("branch/requests/<int:request_id>/lines/", console_views.request_add_line, name="request_add_line"),
    path("branch/requests/<int:request_id>/lines/<int:line_id>/", console_views.request_update_line, name="request_update_line"),
    path("branch/requests/<int:request_id>/lines/<int:line_id>/remove/", console_views.request_remove_line, name="request_remove_line"),
    path("branch/requests/<int:request_id>/submit/", console_views.request_submit, name="request_submit"),
    path("branch/requests/<int:request_id>/approve/", console_views.request_approve, name="request_approve"),
    path("branch/requests/<int:request_id>/reject/", console_views.request_reject, name="request_reject"),
    path("branch/requests/<int:request_id>/cancel/", console_views.request_cancel, name="request_cancel"),
    path("branch/requests/<int:request_id>/history/", console_views.request_history, name="request_history"),
    path("manage/internal-requests/", console_views.warehouse_request_list, name="warehouse_request_list"),
    path("manage/internal-requests/<int:request_id>/", console_views.warehouse_request_detail, name="warehouse_request_detail"),
    path("manage/internal-requests/<int:request_id>/issue/", console_views.warehouse_request_issue, name="warehouse_request_issue"),
    path("manage/internal-requests/<int:request_id>/short-close/", console_views.warehouse_request_short_close, name="warehouse_request_short_close"),
    path("manage/branch-approval-limits/", console_views.branch_approval_limit_list, name="branch_approval_limit_list"),
]
