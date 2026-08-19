from django.contrib.admin import AdminSite
from django.contrib.admin.apps import AdminConfig


class SuperuserAdminSite(AdminSite):
    """Admin site restricted to superusers (staff users cannot log in)."""

    def has_permission(self, request):
        return bool(request.user.is_active and request.user.is_superuser)


class CentComprasAdminConfig(AdminConfig):
    default_site = "accounts.admin_site.SuperuserAdminSite"
