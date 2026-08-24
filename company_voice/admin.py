from django.contrib import admin

from .models import VoiceComment, VoicePost, VoiceSubThread


@admin.register(VoicePost)
class VoicePostAdmin(admin.ModelAdmin):
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
        "deleted_at",
    )


@admin.register(VoiceSubThread)
class VoiceSubThreadAdmin(admin.ModelAdmin):
    list_display = ("id", "post", "created_at", "deleted_at")
    list_filter = ("deleted_at",)
    readonly_fields = ("post", "created_at", "deleted_at")


@admin.register(VoiceComment)
class VoiceCommentAdmin(admin.ModelAdmin):
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
        "deleted_at",
    )
