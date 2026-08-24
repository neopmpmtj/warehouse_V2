"""
Google OAuth views (login-only).

Handles the Google Sign-In flow for an internal staff app:
- GoogleLoginView: start OAuth -> Google consent screen
- GoogleCallbackView: exchange code, fetch profile, log in EXISTING users only
  (no open signup / auto-create). Existing password users go through a
  one-time link-confirm step so the Google identity cannot be attached to an
  account without proving knowledge of its password.
- GoogleLinkConfirmView: password confirmation for linking.

AUTH_MODE setting:
- "both" (default, dev + initial prod): password login and Google both allowed
- "google_only" (final prod): password login disabled; Google is the only method
"""

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.shortcuts import redirect, render
from django.utils.translation import gettext_lazy as _
from django.views import View

from logging_utils import get_logger

from .google_auth import (
    GoogleAuthError,
    create_authorization_url,
    exchange_code_for_tokens,
    get_google_user_info,
)
from .models import User

logger = get_logger("centcompras.accounts")


class GoogleLoginView(View):
    """GET /accounts/google/login/ — start OAuth flow (Google consent screen)."""

    def get(self, request):
        if request.user.is_authenticated:
            messages.info(request, _("You are already logged in."))
            return redirect(settings.LOGIN_REDIRECT_URL)

        try:
            auth_url, state = create_authorization_url(request=request)
            request.session["oauth_state"] = state
            request.session["oauth_flow"] = "login"
            logger.debug("Redirecting to Google OAuth")
            return redirect(auth_url)
        except GoogleAuthError as e:
            logger.error(f"Failed to create authorization URL: {e}")
            messages.error(request, _("Unable to connect to Google. Please try again."))
            return redirect("login")


class GoogleCallbackView(View):
    """GET /accounts/google/callback/ — handle the OAuth callback."""

    def get(self, request):
        error = request.GET.get("error")
        if error:
            messages.error(request, _("Google sign-in was cancelled or failed."))
            return redirect("login")

        state = request.GET.get("state")
        stored_state = request.session.get("oauth_state")
        if not state or state != stored_state:
            logger.warning("OAuth state mismatch — possible CSRF attack")
            messages.error(request, _("Invalid authentication request. Please try again."))
            return redirect("login")

        code = request.GET.get("code")
        if not code:
            logger.warning("No authorization code in callback")
            messages.error(request, _("Invalid authentication response. Please try again."))
            return redirect("login")

        try:
            tokens = exchange_code_for_tokens(code, request)
            access_token = tokens.get("access_token")
            if not access_token:
                raise GoogleAuthError("No access token in response")

            user_info = get_google_user_info(access_token)
            google_email = (user_info.get("email") or "").lower()
            if not google_email:
                raise GoogleAuthError("No email in user info")
            if not user_info.get("email_verified"):
                messages.error(request, _("Please verify your Google account email first."))
                return redirect("login")

            # EXISTING-ONLY: no auto-create. Google login is for staff accounts
            # that already exist in the app (seeded/created by an admin).
            user = User.objects.filter(email=google_email).first()
            if user is None:
                logger.warning(f"Google login blocked: no account for {google_email}")
                messages.error(
                    request,
                    _(
                        "No CentCompras account exists for this Google email. "
                        "Ask an administrator to create one, then try again."
                    ),
                )
                return redirect("login")

            if user.has_usable_password() and not user.is_google_account:
                # Existing password user proving ownership once before linking.
                request.session["google_link_data"] = {
                    "email": google_email,
                    "user_info": user_info,
                }
                return redirect("google_link_confirm")

            self._login_google_user(request, user, user_info)
            messages.success(request, _("Welcome back!"))
            return redirect(settings.LOGIN_REDIRECT_URL)

        except GoogleAuthError as e:
            logger.error(f"Google OAuth error: {e}")
            messages.error(request, _("Google sign-in failed. Please try again."))
            return redirect("login")
        finally:
            request.session.pop("oauth_state", None)

    def _login_google_user(self, request, user, user_info):
        if not user.first_name and user_info.get("given_name"):
            user.first_name = user_info["given_name"]
        if not user.last_name and user_info.get("family_name"):
            user.last_name = user_info["family_name"]
        user.is_google_account = True
        user.is_email_verified = True
        user.save(update_fields=["first_name", "last_name", "is_google_account", "is_email_verified"])
        login(request, user)
        logger.info(f"Google user logged in: {user.email}")


class GoogleLinkConfirmView(View):
    """GET/POST /accounts/google/link-confirm/ — prove password before linking."""

    template_name = "accounts/google_link_confirm.html"

    def get(self, request):
        link_data = request.session.get("google_link_data")
        if not link_data:
            messages.error(request, _("No pending account link. Please try again."))
            return redirect("login")
        return render(request, self.template_name, {"email": link_data["email"]})

    def post(self, request):
        link_data = request.session.get("google_link_data")
        if not link_data:
            messages.error(request, _("No pending account link. Please try again."))
            return redirect("login")

        email = link_data["email"]
        user = User.objects.filter(email=email).first()
        if user is None:
            request.session.pop("google_link_data", None)
            messages.error(request, _("Account not found. Please try again."))
            return redirect("login")

        password = request.POST.get("password", "")
        if not user.check_password(password):
            messages.error(request, _("Incorrect password. Please try again."))
            return render(request, self.template_name, {"email": email})

        user_info = link_data.get("user_info", {})
        if not user.first_name and user_info.get("given_name"):
            user.first_name = user_info["given_name"]
        if not user.last_name and user_info.get("family_name"):
            user.last_name = user_info["family_name"]
        user.is_google_account = True
        user.is_email_verified = True
        user.save(update_fields=["first_name", "last_name", "is_google_account", "is_email_verified"])

        request.session.pop("google_link_data", None)
        login(request, user)
        logger.info(f"Linked Google account for user: {user.email}")
        messages.success(request, _("Your Google account has been linked successfully!"))
        return redirect(settings.LOGIN_REDIRECT_URL)
