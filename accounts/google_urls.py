"""Google OAuth URL patterns (login-only — no service connect/disconnect)."""

from django.urls import path

from . import google_views

# Full paths: /accounts/google/login/, /accounts/google/callback/,
# /accounts/google/link-confirm/
urlpatterns = [
    path("login/", google_views.GoogleLoginView.as_view(), name="google_login"),
    path("callback/", google_views.GoogleCallbackView.as_view(), name="google_callback"),
    path(
        "link-confirm/",
        google_views.GoogleLinkConfirmView.as_view(),
        name="google_link_confirm",
    ),
]
