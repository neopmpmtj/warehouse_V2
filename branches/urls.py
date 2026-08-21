from django.urls import path

from . import console_views

urlpatterns = [
    path(
        "branch/catalog/",
        console_views.branch_catalog_list,
        name="branch_catalog_list",
    ),
]
