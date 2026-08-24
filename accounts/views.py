from django.conf import settings
from django.contrib import messages
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from django.contrib.sessions.models import Session
from django.shortcuts import redirect
from django.views.decorators.http import require_POST

from .throttle import clear_failures, is_login_locked, record_failure


def _client_ip(request):
    return request.META.get("REMOTE_ADDR", "")


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
        # H2 rate limiting: refuse before authenticate() runs.
        if request.method == "POST":
            username = request.POST.get("username", "")
            if username and is_login_locked(username):
                messages.error(
                    request,
                    "Too many failed attempts. Please try again later.",
                )
                return redirect("login")
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        clear_failures(form.cleaned_data.get("username", ""))
        return super().form_valid(form)

    def form_invalid(self, form):
        username = self.request.POST.get("username", "")
        if username:
            record_failure(username, ip=_client_ip(self.request))
        return super().form_invalid(form)


@require_POST
@login_required
def logout_other_devices(request):
    """Delete all sessions for the current user except this one.

    M7: "log out other devices" from the account settings popover.
    Independent per-device sessions remain the default; this is the
    user-triggered revocation path.
    """
    user = request.user
    current_key = request.session.session_key
    for session in Session.objects.all():
        try:
            data = session.get_decoded()
        except Exception:
            continue
        if (
            str(data.get("_auth_user_id", "")) == str(user.pk)
            and session.session_key != current_key
        ):
            session.delete()
    messages.success(request, "Other devices have been signed out.")
    return redirect(request.POST.get("next") or settings.LOGIN_REDIRECT_URL)
