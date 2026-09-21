from django.contrib import admin

from .models import SectionCursor


class SuperuserReadOnlyMixin:
    def has_module_permission(self, request):
        return request.user.is_superuser

    def has_view_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request):
        return False


@admin.register(SectionCursor)
class SectionCursorAdmin(SuperuserReadOnlyMixin, admin.ModelAdmin):
    list_display = ("id", "user", "section", "branch", "last_seen_at")
    list_filter = ("section",)
    search_fields = ("user__email",)
    readonly_fields = ("user", "section", "branch", "last_seen_at")
