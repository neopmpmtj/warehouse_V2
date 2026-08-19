from django.urls import path

from . import console_views, views


urlpatterns = [
    path("", views.staff_dashboard, name="staff_dashboard"),
    path(
        "manage/items/",
        console_views.item_console,
        name="item_console",
    ),
    path(
        "service-worker.js",
        views.service_worker,
        name="service_worker",
    ),
]
