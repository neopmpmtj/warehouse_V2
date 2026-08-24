from django.contrib.auth import views as auth_views
from django.urls import include, path

from .views import LoginView, logout_other_devices

urlpatterns = [
    path(
        "login/",
        LoginView.as_view(),
        name="login",
    ),
    path(
        "logout/",
        auth_views.LogoutView.as_view(),
        name="logout",
    ),
    path(
        "sessions/logout-other/",
        logout_other_devices,
        name="logout_other_devices",
    ),
    path("google/", include("accounts.google_urls")),
]
