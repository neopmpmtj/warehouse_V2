from django.contrib import admin

from .models import GoodsReceipt, GoodsReceiptLine, StockMovement


class GoodsReceiptLineInline(admin.TabularInline):
    model = GoodsReceiptLine
    extra = 0
    can_delete = False
    readonly_fields = ("purchase_order_line", "quantity_received", "created_at")

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(GoodsReceipt)
class GoodsReceiptAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "purchase_order",
        "received_by",
        "received_at",
        "reference",
    )
    list_filter = ("received_at",)
    search_fields = ("reference", "purchase_order__id", "purchase_order__supplier__name")
    inlines = (GoodsReceiptLineInline,)
    readonly_fields = (
        "purchase_order",
        "received_by",
        "received_at",
        "reference",
        "notes",
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


@admin.register(StockMovement)
class StockMovementAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "item",
        "movement_type",
        "quantity",
        "created_by",
        "created_at",
    )
    list_filter = ("movement_type",)
    search_fields = ("item__internal_code", "item__description", "reason")
    readonly_fields = (
        "item",
        "quantity",
        "movement_type",
        "content_type",
        "object_id",
        "reason",
        "created_by",
        "created_at",
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
