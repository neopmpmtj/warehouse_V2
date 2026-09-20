from urllib.parse import urlparse

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from django.contrib.sessions.models import Session
from django.shortcuts import redirect
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from .throttle import clear_failures, is_login_locked, record_failure


def _client_ip(request):
    return request.META.get("REMOTE_ADDR", "")


def landing_url(request):
    """Role landing after login (lock 5). Warehouse/dual → `/`; branch-only → `/branch/`."""
    from branches.services import post_login_landing

    return post_login_landing(request) or settings.LOGIN_REDIRECT_URL


def next_usable_for_user(request, url):
    """True when this signed-in user can open ``url`` (not a warehouse-only trap)."""
    if not url:
        return False
    from products.permissions import can_view_catalog

    path = urlparse(url).path or "/"
    if path == "/" or path.startswith("/manage/"):
        return can_view_catalog(request.user)
    return True


class LoginView(auth_views.LoginView):
    template_name = "accounts/login.html"
    redirect_authenticated_user = True

    def get_success_url(self):
        # Honor `next` only when this user can open it; otherwise lock 5.
        url = self.get_redirect_url()
        if url and next_usable_for_user(self.request, url):
            return url
        return landing_url(self.request)

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
            if google_configured and not request.user.is_authenticated:
                return redirect("google_login")
            if not google_configured:
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
    now = timezone.now()
    for session in Session.objects.filter(expire_date__gte=now).iterator(chunk_size=500):
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
    next_url = request.POST.get("next") or ""
    if (
        next_url
        and url_has_allowed_host_and_scheme(
            next_url,
            allowed_hosts={request.get_host()},
            require_https=request.is_secure(),
        )
        and next_usable_for_user(request, next_url)
    ):
        return redirect(next_url)
    return redirect(landing_url(request))
