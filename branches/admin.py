from django.contrib import admin

from .models import Branch, BranchCommercialSettings, BranchMembership


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


@admin.register(BranchCommercialSettings)
class BranchCommercialSettingsAdmin(admin.ModelAdmin):
    list_display = ("mode", "updated_at")
    fields = ("mode", "updated_at")
    readonly_fields = ("updated_at",)

    def has_add_permission(self, request):
        return not BranchCommercialSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False

    def save_model(self, request, obj, form, change):
        from .services import set_branch_commercial_mode

        mode = form.cleaned_data.get("mode") if form is not None else obj.mode
        set_branch_commercial_mode(mode)
