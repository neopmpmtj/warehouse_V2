from django.urls import path

from . import views

urlpatterns = [
    path("", views.branch_dashboard, name="branch_dashboard"),
    path("select/", views.branch_select, name="branch_select"),
    path("catalog/", views.branch_catalog, name="branch_catalog"),
]
