from django.contrib import admin

from .models import VoiceChangeLog, VoiceComment, VoicePost, VoiceSubThread


class SuperuserReadOnlyMixin:
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


class VoiceChangeLogInline(admin.TabularInline):
    model = VoiceChangeLog
    extra = 0
    can_delete = False
    readonly_fields = ("user", "action", "comment", "changes", "created_at")
    ordering = ("-created_at",)

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(VoicePost)
class VoicePostAdmin(SuperuserReadOnlyMixin, admin.ModelAdmin):
    list_display = (
        "id",
        "author",
        "tag",
        "is_anonymous",
        "created_at",
        "deleted_at",
    )
    list_filter = ("tag", "is_anonymous", "deleted_at")
    search_fields = ("body", "author__email")
    readonly_fields = (
        "author",
        "body",
        "tag",
        "is_anonymous",
        "created_at",
        "updated_at",
        "edited_at",
        "deleted_at",
    )
    inlines = (VoiceChangeLogInline,)


@admin.register(VoiceSubThread)
class VoiceSubThreadAdmin(SuperuserReadOnlyMixin, admin.ModelAdmin):
    list_display = ("id", "post", "created_at", "deleted_at")
    list_filter = ("deleted_at",)
    readonly_fields = ("post", "created_at", "deleted_at")


@admin.register(VoiceComment)
class VoiceCommentAdmin(SuperuserReadOnlyMixin, admin.ModelAdmin):
    list_display = (
        "id",
        "sub_thread",
        "author",
        "is_anonymous",
        "created_at",
        "deleted_at",
    )
    list_filter = ("is_anonymous", "deleted_at")
    search_fields = ("body", "author__email")
    readonly_fields = (
        "sub_thread",
        "author",
        "body",
        "is_anonymous",
        "created_at",
        "updated_at",
        "edited_at",
        "deleted_at",
    )


@admin.register(VoiceChangeLog)
class VoiceChangeLogAdmin(SuperuserReadOnlyMixin, admin.ModelAdmin):
    list_display = ("id", "post", "comment", "user", "action", "created_at")
    list_filter = ("action",)
    search_fields = ("post__id", "user__email")
    readonly_fields = ("post", "comment", "user", "action", "changes", "created_at")
