from django.conf import settings
from django.contrib.auth import views as auth_views


class LoginView(auth_views.LoginView):
    template_name = "accounts/login.html"

    def get_success_url(self):
        # Honor an explicit `next` first; otherwise route by role (lock 5).
        url = self.get_redirect_url()
        if url:
            return url
        from branches.services import post_login_landing

        return post_login_landing(self.request) or settings.LOGIN_REDIRECT_URL
