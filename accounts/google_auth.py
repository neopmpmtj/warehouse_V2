"""
Google OAuth login helpers (login-only — no Gmail/Drive/Calendar).

Trimmed from the Voice Diary `google_account` module: this app only needs
Google Sign-In (openid + email + profile) so users can log in safely with
their Google account. No service scopes, no token storage, no refresh flow.

Pure stdlib (urllib) — no google-api-* dependencies required.
"""

import json
import secrets
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlencode
from urllib.request import Request as URLRequest
from urllib.request import urlopen
from urllib.error import HTTPError, URLError

from django.conf import settings
from django.urls import reverse

# --- Scopes (login only: "the name") ---
OPENID_SCOPE = "openid"
EMAIL_SCOPE = "https://www.googleapis.com/auth/userinfo.email"
PROFILE_SCOPE = "https://www.googleapis.com/auth/userinfo.profile"

LOGIN_SCOPES = [OPENID_SCOPE, EMAIL_SCOPE, PROFILE_SCOPE]

# --- OAuth endpoints ---
GOOGLE_AUTH_URI = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URI = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URI = "https://www.googleapis.com/oauth2/v3/userinfo"

GOOGLE_API_TIMEOUT = 30


class GoogleAuthError(Exception):
    """Raised for Google OAuth failures (config, network, token, userinfo)."""


def get_google_client_config() -> Dict[str, str]:
    """Return client_id/client_secret from settings, or raise if unset."""
    client_id = getattr(settings, "GOOGLE_CLIENT_ID", None)
    client_secret = getattr(settings, "GOOGLE_CLIENT_SECRET", None)
    if not client_id or not client_secret:
        raise GoogleAuthError(
            "Google OAuth credentials not configured. "
            "Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET in .env / settings."
        )
    return {"client_id": client_id, "client_secret": client_secret}


def get_redirect_uri(request=None) -> str:
    """Callback URI: settings override, else built from the request.

    Works for both a Desktop-app client (loopback, e.g.
    http://localhost:8000/accounts/google/callback/) and a Web-app client
    (https://domain/accounts/google/callback/). Set GOOGLE_OAUTH_REDIRECT_URI
    in .env to match what is registered in Google Cloud Console.
    """
    redirect_uri = getattr(settings, "GOOGLE_OAUTH_REDIRECT_URI", None)
    if redirect_uri:
        return redirect_uri
    if request is not None:
        return request.build_absolute_uri(reverse("google_callback"))
    return "http://localhost:8000/accounts/google/callback/"


def create_authorization_url(
    request=None,
    scopes: Optional[List[str]] = None,
    state: Optional[str] = None,
    login_hint: Optional[str] = None,
) -> Tuple[str, str]:
    """Build the Google consent URL. Returns (authorization_url, state)."""
    client_config = get_google_client_config()
    redirect_uri = get_redirect_uri(request)
    request_scopes = scopes or LOGIN_SCOPES

    if state is None:
        state = secrets.token_urlsafe(32)

    params = {
        "client_id": client_config["client_id"],
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": " ".join(request_scopes),
        "state": state,
        "access_type": "online",  # login-only: no refresh token needed
        "prompt": "select_account",  # let the user pick an account each time
    }
    if login_hint:
        params["login_hint"] = login_hint

    return f"{GOOGLE_AUTH_URI}?{urlencode(params)}", state


def exchange_code_for_tokens(code: str, request=None) -> Dict[str, Any]:
    """Exchange the authorization code for an access token."""
    client_config = get_google_client_config()
    redirect_uri = get_redirect_uri(request)

    token_data = {
        "code": code,
        "client_id": client_config["client_id"],
        "client_secret": client_config["client_secret"],
        "redirect_uri": redirect_uri,
        "grant_type": "authorization_code",
    }

    try:
        data = urlencode(token_data).encode("utf-8")
        req = URLRequest(GOOGLE_TOKEN_URI, data=data, method="POST")
        req.add_header("Content-Type", "application/x-www-form-urlencoded")
        with urlopen(req, timeout=GOOGLE_API_TIMEOUT) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as e:
        error_body = e.read().decode("utf-8") if e.fp else str(e)
        raise GoogleAuthError(f"Failed to exchange code for tokens: {error_body}")
    except (URLError, TimeoutError) as e:
        raise GoogleAuthError(f"Network error during token exchange: {e}")
    except json.JSONDecodeError:
        raise GoogleAuthError("Invalid response from Google token endpoint")


def get_google_user_info(access_token: str) -> Dict[str, Any]:
    """Fetch profile info (sub, email, email_verified, name, picture)."""
    try:
        req = URLRequest(GOOGLE_USERINFO_URI)
        req.add_header("Authorization", f"Bearer {access_token}")
        with urlopen(req, timeout=GOOGLE_API_TIMEOUT) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as e:
        error_body = e.read().decode("utf-8") if e.fp else str(e)
        raise GoogleAuthError(f"Failed to fetch user info: {error_body}")
    except (URLError, TimeoutError) as e:
        raise GoogleAuthError(f"Network error fetching user info: {e}")
    except json.JSONDecodeError:
        raise GoogleAuthError("Invalid response from Google userinfo endpoint")
