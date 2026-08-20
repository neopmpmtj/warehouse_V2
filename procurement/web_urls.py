from django.urls import path

from . import views

urlpatterns = [
    path(
        "manage/purchase-orders/",
        views.purchase_order_console,
        name="purchase_order_console",
    ),
]
