from django.urls import path

from . import views

urlpatterns = [
    path(
        "manage/goods-receipts/",
        views.goods_receipt_console,
        name="goods_receipt_console",
    ),
    path(
        "branch/receipts/",
        views.branch_receipt_console,
        name="branch_receipt_console",
    ),
]
