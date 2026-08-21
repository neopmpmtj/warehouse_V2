from django.contrib import admin

from .models import Branch, BranchMembership


@admin.register(Branch)
class BranchAdmin(admin.ModelAdmin):
    list_display = ("name", "is_active", "created_at", "updated_at")
    list_filter = ("is_active",)
    search_fields = ("name",)


@admin.register(BranchMembership)
class BranchMembershipAdmin(admin.ModelAdmin):
    list_display = ("user", "branch", "role", "created_at")
    list_filter = ("role", "branch")
    search_fields = ("user__email", "branch__name")
    list_select_related = ("user", "branch")
