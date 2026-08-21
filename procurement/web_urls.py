from django.urls import path

from . import views

urlpatterns = [
    path(
        "manage/purchase-orders/",
        views.purchase_order_console,
        name="purchase_order_console",
    ),
    path(
        "manage/approval-limits/",
        views.approval_limit_console,
        name="approval_limit_console",
    ),
]
