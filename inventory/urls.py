from django.urls import path

from . import console_views

urlpatterns = [
    path(
        "manage/goods-receipts/",
        console_views.manage_goods_receipt_list,
        name="manage_goods_receipt_list",
    ),
    path(
        "manage/goods-receipts/<int:receipt_id>/",
        console_views.manage_goods_receipt_detail,
        name="manage_goods_receipt_detail",
    ),
    path(
        "manage/purchase-orders/<int:po_id>/receipt-summary/",
        console_views.manage_receipt_summary,
        name="manage_receipt_summary",
    ),
    path(
        "manage/stock-movements/",
        console_views.manage_stock_movements,
        name="manage_stock_movements",
    ),
    path(
        "manage/stock-adjustments/",
        console_views.manage_stock_adjustment,
        name="manage_stock_adjustment",
    ),
    path(
        "branch/receipts/issues/",
        console_views.branch_receipt_issue_list,
        name="branch_receipt_issue_list",
    ),
    path(
        "branch/receipts/issues/<int:issue_id>/",
        console_views.branch_receipt_issue_detail,
        name="branch_receipt_issue_detail",
    ),
    path(
        "branch/receipts/issues/<int:issue_id>/receive/",
        console_views.branch_receipt_receive,
        name="branch_receipt_receive",
    ),
    path(
        "branch/receipts/issues/<int:issue_id>/short-close/",
        console_views.branch_receipt_short_close,
        name="branch_receipt_short_close",
    ),
    path(
        "branch/stock/adjust/",
        console_views.branch_stock_adjust,
        name="branch_stock_adjust",
    ),
]
