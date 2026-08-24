from django.urls import path

from . import views

urlpatterns = [
    path("threads/", views.branch_thread_console, name="branch_thread_console"),
]
