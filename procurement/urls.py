from django.urls import path

from . import console_views

urlpatterns = [
    path(
        "manage/purchase-orders/",
        console_views.manage_purchase_order_list,
        name="manage_purchase_order_list",
    ),
    path(
        "manage/purchase-orders/<int:po_id>/",
        console_views.manage_purchase_order_detail,
        name="manage_purchase_order_detail",
    ),
    path(
        "manage/purchase-orders/<int:po_id>/lines/",
        console_views.manage_purchase_order_lines,
        name="manage_purchase_order_lines",
    ),
    path(
        "manage/purchase-orders/<int:po_id>/lines/<int:line_id>/",
        console_views.manage_purchase_order_line_detail,
        name="manage_purchase_order_line_detail",
    ),
    path(
        "manage/purchase-orders/<int:po_id>/submit/",
        console_views.manage_purchase_order_submit,
        name="manage_purchase_order_submit",
    ),
    path(
        "manage/purchase-orders/<int:po_id>/approve/",
        console_views.manage_purchase_order_approve,
        name="manage_purchase_order_approve",
    ),
    path(
        "manage/purchase-orders/<int:po_id>/reject/",
        console_views.manage_purchase_order_reject,
        name="manage_purchase_order_reject",
    ),
    path(
        "manage/purchase-orders/<int:po_id>/reopen/",
        console_views.manage_purchase_order_reopen,
        name="manage_purchase_order_reopen",
    ),
    path(
        "manage/purchase-orders/<int:po_id>/close/",
        console_views.manage_purchase_order_close,
        name="manage_purchase_order_close",
    ),
    path(
        "manage/purchase-orders/<int:po_id>/history/",
        console_views.manage_purchase_order_history,
        name="manage_purchase_order_history",
    ),
]
