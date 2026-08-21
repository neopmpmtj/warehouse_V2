from django.urls import path

from . import views

urlpatterns = [
    path("requests/", views.request_console, name="request_console"),
]
