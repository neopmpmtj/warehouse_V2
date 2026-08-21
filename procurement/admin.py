from django.contrib import admin

from .models import (
    ApprovalLimit,
    ApprovalLimitChangeLog,
    PurchaseOrder,
    PurchaseOrderChangeLog,
    PurchaseOrderLine,
)


class PurchaseOrderLineInline(admin.TabularInline):
    model = PurchaseOrderLine
    extra = 0
    fields = (
        "item",
        "internal_code",
        "description",
        "quantity",
        "unit_cost",
        "discount_commercial",
        "discount_financial",
        "rappel",
    )
    readonly_fields = fields
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False


class PurchaseOrderChangeLogInline(admin.TabularInline):
    model = PurchaseOrderChangeLog
    extra = 0
    can_delete = False
    readonly_fields = ("user", "action", "reason", "changes", "created_at")
    ordering = ("-created_at",)

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(PurchaseOrder)
class PurchaseOrderAdmin(admin.ModelAdmin):
    list_display = ("id", "supplier", "status", "created_by", "approved_by", "created_at")
    list_filter = ("status", "supplier")
    search_fields = ("id", "supplier__name", "supplier_ref")
    readonly_fields = (
        "supplier",
        "status",
        "created_by",
        "approved_by",
        "approved_at",
        "created_at",
        "updated_at",
    )
    inlines = (PurchaseOrderLineInline, PurchaseOrderChangeLogInline)
    fieldsets = (
        (None, {"fields": ("supplier", "status", "supplier_ref", "notes")}),
        (
            "People & dates",
            {"fields": ("created_by", "approved_by", "approved_at", "created_at", "updated_at")},
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


@admin.register(PurchaseOrderChangeLog)
class PurchaseOrderChangeLogAdmin(admin.ModelAdmin):
    list_display = ("id", "purchase_order", "user", "action", "created_at")
    list_filter = ("action",)
    search_fields = ("purchase_order__id", "purchase_order__supplier__name", "user__email")
    readonly_fields = ("purchase_order", "user", "action", "reason", "changes", "created_at")

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


@admin.register(ApprovalLimit)
class ApprovalLimitAdmin(admin.ModelAdmin):
    list_display = ("id", "group_name", "grade", "approval_limit", "self_approval_limit", "updated_at")
    readonly_fields = ("group_name", "grade", "approval_limit", "self_approval_limit", "updated_at")

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


@admin.register(ApprovalLimitChangeLog)
class ApprovalLimitChangeLogAdmin(admin.ModelAdmin):
    list_display = ("id", "approval_limit", "user", "action", "created_at")
    readonly_fields = ("approval_limit", "user", "action", "changes", "created_at")

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
