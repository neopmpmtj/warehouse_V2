from django.contrib import admin

from .models import (
    ItemRequestThread,
    ItemRequestThreadChangeLog,
    ThreadMessage,
    ThreadReadState,
)


class ThreadMessageInline(admin.TabularInline):
    model = ThreadMessage
    extra = 0
    fields = ("author", "side", "body", "created_at")
    readonly_fields = fields
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False


class ItemRequestThreadChangeLogInline(admin.TabularInline):
    model = ItemRequestThreadChangeLog
    extra = 0
    can_delete = False
    readonly_fields = ("user", "action", "reason", "changes", "created_at")
    ordering = ("-created_at",)

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(ItemRequestThread)
class ItemRequestThreadAdmin(admin.ModelAdmin):
    list_display = ("id", "subject", "branch", "status", "opened_by", "message_count", "last_activity_at")
    list_filter = ("status", "branch")
    search_fields = ("id", "subject", "branch__name", "opened_by__email")
    readonly_fields = (
        "branch",
        "opened_by",
        "subject",
        "status",
        "last_activity_at",
        "message_count",
        "closed_by",
        "closed_at",
        "close_reason",
        "close_reason_text",
        "items",
        "created_at",
        "updated_at",
    )
    inlines = (ThreadMessageInline, ItemRequestThreadChangeLogInline)
    fieldsets = (
        (None, {"fields": ("branch", "opened_by", "subject", "status")}),
        (
            "Activity",
            {
                "fields": (
                    "last_activity_at",
                    "message_count",
                    "created_at",
                    "updated_at",
                )
            },
        ),
        (
            "Close",
            {
                "fields": (
                    "closed_by",
                    "closed_at",
                    "close_reason",
                    "close_reason_text",
                )
            },
        ),
        ("Traceability", {"fields": ("items",)}),
    )

    def has_module_permission(self, request):
        return request.user.is_superuser

    def has_view_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(ThreadMessage)
class ThreadMessageAdmin(admin.ModelAdmin):
    list_display = ("id", "thread", "author", "side", "created_at")
    list_filter = ("side",)
    search_fields = ("thread__id", "thread__subject", "author__email")
    readonly_fields = ("thread", "author", "side", "body", "created_at")

    def has_module_permission(self, request):
        return request.user.is_superuser

    def has_view_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(ThreadReadState)
class ThreadReadStateAdmin(admin.ModelAdmin):
    list_display = ("id", "thread", "user", "last_read_at")
    search_fields = ("thread__id", "user__email")
    readonly_fields = ("thread", "user", "last_read_at")

    def has_module_permission(self, request):
        return request.user.is_superuser

    def has_view_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(ItemRequestThreadChangeLog)
class ItemRequestThreadChangeLogAdmin(admin.ModelAdmin):
    list_display = ("id", "thread", "user", "action", "created_at")
    list_filter = ("action",)
    search_fields = ("thread__id", "user__email")
    readonly_fields = ("thread", "user", "action", "reason", "changes", "created_at")

    def has_module_permission(self, request):
        return request.user.is_superuser

    def has_view_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
