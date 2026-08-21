from django.contrib import admin

from .models import (
    BranchApprovalLimit,
    BranchApprovalLimitChangeLog,
    InternalRequest,
    InternalRequestChangeLog,
    InternalRequestLine,
    InternalRequestLineChangeLog,
)


class InternalRequestLineInline(admin.TabularInline):
    model = InternalRequestLine
    extra = 0
    fields = (
        "item",
        "internal_code",
        "description",
        "quantity",
        "unit_price",
        "vat_rate",
    )
    readonly_fields = fields
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False


class InternalRequestChangeLogInline(admin.TabularInline):
    model = InternalRequestChangeLog
    extra = 0
    can_delete = False
    readonly_fields = ("user", "action", "reason", "changes", "created_at")
    ordering = ("-created_at",)

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(InternalRequest)
class InternalRequestAdmin(admin.ModelAdmin):
    list_display = ("id", "branch", "status", "created_by", "approved_by", "created_at")
    list_filter = ("status", "branch")
    search_fields = ("id", "branch__name", "created_by__email")
    readonly_fields = (
        "branch",
        "status",
        "created_by",
        "submitted_by",
        "approved_by",
        "submitted_at",
        "approved_at",
        "approved_net",
        "approved_vat",
        "approved_gross",
        "created_at",
        "updated_at",
    )
    inlines = (InternalRequestLineInline, InternalRequestChangeLogInline)
    fieldsets = (
        (None, {"fields": ("branch", "status", "notes", "warehouse_notes")}),
        (
            "People & totals",
            {
                "fields": (
                    "created_by",
                    "submitted_by",
                    "approved_by",
                    "submitted_at",
                    "approved_at",
                    "approved_net",
                    "approved_vat",
                    "approved_gross",
                    "created_at",
                    "updated_at",
                )
            },
        ),
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


@admin.register(InternalRequestChangeLog)
class InternalRequestChangeLogAdmin(admin.ModelAdmin):
    list_display = ("id", "internal_request", "user", "action", "created_at")
    list_filter = ("action",)
    search_fields = ("internal_request__id", "user__email")
    readonly_fields = ("internal_request", "user", "action", "reason", "changes", "created_at")

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


@admin.register(InternalRequestLineChangeLog)
class InternalRequestLineChangeLogAdmin(admin.ModelAdmin):
    list_display = ("id", "internal_request_line", "user", "action", "created_at")
    list_filter = ("action",)
    readonly_fields = ("internal_request_line", "user", "action", "reason", "changes", "created_at")

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


@admin.register(BranchApprovalLimit)
class BranchApprovalLimitAdmin(admin.ModelAdmin):
    list_display = ("id", "role", "approval_limit", "self_approval_limit", "updated_at")
    readonly_fields = ("role", "approval_limit", "self_approval_limit", "updated_at")

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


@admin.register(BranchApprovalLimitChangeLog)
class BranchApprovalLimitChangeLogAdmin(admin.ModelAdmin):
    list_display = ("id", "branch_approval_limit", "user", "action", "created_at")
    readonly_fields = ("branch_approval_limit", "user", "action", "changes", "created_at")

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
