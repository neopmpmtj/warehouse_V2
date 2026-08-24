from django.conf import settings
from django.contrib import messages
from django.contrib.auth import views as auth_views
from django.shortcuts import redirect


class LoginView(auth_views.LoginView):
    template_name = "accounts/login.html"

    def get_success_url(self):
        # Honor an explicit `next` first; otherwise route by role (lock 5).
        url = self.get_redirect_url()
        if url:
            return url
        from branches.services import post_login_landing

        return post_login_landing(self.request) or settings.LOGIN_REDIRECT_URL

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["auth_mode"] = getattr(settings, "AUTH_MODE", "both")
        context["google_configured"] = bool(
            getattr(settings, "GOOGLE_CLIENT_ID", "")
            and getattr(settings, "GOOGLE_CLIENT_SECRET", "")
        )
        return context

    def dispatch(self, request, *args, **kwargs):
        # AUTH_MODE=google_only: password login is disabled — send users to Google.
        if getattr(settings, "AUTH_MODE", "both") == "google_only":
            google_configured = bool(
                getattr(settings, "GOOGLE_CLIENT_ID", "")
                and getattr(settings, "GOOGLE_CLIENT_SECRET", "")
            )
            if google_configured:
                return redirect("google_login")
            # No credentials yet: fall through so the template can explain.
            messages.error(request, "Google login is not configured yet.")
        return super().dispatch(request, *args, **kwargs)
