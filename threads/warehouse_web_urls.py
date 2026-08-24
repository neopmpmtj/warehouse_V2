from django.urls import path

from . import views

urlpatterns = [
    path("manage/threads/", views.warehouse_thread_console, name="warehouse_thread_console"),
]
