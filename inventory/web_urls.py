from django.urls import path

from . import views

urlpatterns = [
    path(
        "manage/goods-receipts/",
        views.goods_receipt_console,
        name="goods_receipt_console",
    ),
    path(
        "manage/alerts/",
        views.warehouse_alerts_console,
        name="warehouse_alerts_console",
    ),
    path(
        "branch/receipts/",
        views.branch_receipt_console,
        name="branch_receipt_console",
    ),
    path(
        "branch/stock/",
        views.branch_stock_console,
        name="branch_stock_console",
    ),
    path(
        "branch/consumption/",
        views.branch_consumption_console,
        name="branch_consumption_console",
    ),
    path(
        "branch/alerts/",
        views.branch_alerts_console,
        name="branch_alerts_console",
    ),
]
