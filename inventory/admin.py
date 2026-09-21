from django.contrib import admin

from .models import (
    BranchConsumption,
    BranchConsumptionLine,
    BranchItemStock,
    BranchReceipt,
    BranchReceiptLine,
    BranchReceiptReadState,
    BranchStockMovement,
    BranchWarehouseShipment,
    BranchWarehouseShipmentChangeLog,
    BranchWarehouseShipmentLine,
    DispatchReturn,
    DispatchReturnChangeLog,
    DispatchReturnLine,
    GoodsIssue,
    GoodsIssueLine,
    GoodsReceipt,
    GoodsReceiptLine,
    InventoryAlert,
    InventoryAlertReadState,
    StockMovement,
)


class GoodsIssueLineInline(admin.TabularInline):
    model = GoodsIssueLine
    extra = 0
    can_delete = False
    readonly_fields = ("internal_request_line", "quantity_issued")

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(GoodsIssue)
class GoodsIssueAdmin(admin.ModelAdmin):
    list_display = ("id", "internal_request", "issued_by", "issued_at", "reference")
    search_fields = ("reference", "internal_request__id", "internal_request__branch__name")
    inlines = (GoodsIssueLineInline,)
    readonly_fields = ("internal_request", "issued_by", "issued_at", "reference", "notes")

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


class BranchReceiptLineInline(admin.TabularInline):
    model = BranchReceiptLine
    extra = 0
    can_delete = False
    readonly_fields = ("goods_issue_line", "quantity_received", "quantity_written_off")

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(BranchReceipt)
class BranchReceiptAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "goods_issue",
        "received_by",
        "received_at",
        "is_critical",
        "follow_up_request",
        "reference",
    )
    search_fields = ("reference", "goods_issue__id", "goods_issue__internal_request__id")
    list_filter = ("is_critical",)
    inlines = (BranchReceiptLineInline,)
    readonly_fields = (
        "goods_issue",
        "received_by",
        "received_at",
        "reference",
        "notes",
        "discrepancy_reason",
        "is_critical",
        "follow_up_request",
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


@admin.register(BranchReceiptReadState)
class BranchReceiptReadStateAdmin(admin.ModelAdmin):
    list_display = ("id", "receipt", "user", "read_at")
    search_fields = ("user__email", "receipt__id")
    readonly_fields = ("receipt", "user", "read_at")

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


@admin.register(BranchItemStock)
class BranchItemStockAdmin(admin.ModelAdmin):
    list_display = ("id", "branch", "item", "quantity", "updated_at")
    list_filter = ("branch",)
    search_fields = ("item__internal_code", "item__description", "branch__name")
    readonly_fields = ("branch", "item", "quantity", "updated_at")

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


@admin.register(BranchStockMovement)
class BranchStockMovementAdmin(admin.ModelAdmin):
    list_display = ("id", "branch", "item", "movement_type", "quantity", "created_by", "created_at")
    list_filter = ("movement_type", "branch")
    search_fields = ("item__internal_code", "item__description", "reason")
    readonly_fields = (
        "branch",
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


class BranchConsumptionLineInline(admin.TabularInline):
    model = BranchConsumptionLine
    extra = 0
    can_delete = False
    readonly_fields = ("item", "quantity")

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(BranchConsumption)
class BranchConsumptionAdmin(admin.ModelAdmin):
    list_display = ("id", "branch", "consumed_by", "consumed_at", "reason")
    search_fields = ("reason", "notes", "branch__name", "consumed_by__email")
    list_filter = ("branch",)
    inlines = (BranchConsumptionLineInline,)
    readonly_fields = (
        "branch",
        "consumed_by",
        "consumed_at",
        "reason",
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


class BranchWarehouseShipmentLineInline(admin.TabularInline):
    model = BranchWarehouseShipmentLine
    extra = 0
    can_delete = False
    readonly_fields = (
        "item",
        "quantity_sent",
        "quantity_received",
        "quantity_written_off",
    )

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(BranchWarehouseShipment)
class BranchWarehouseShipmentAdmin(admin.ModelAdmin):
    list_display = ("id", "branch", "status", "sent_by", "sent_at", "reason")
    search_fields = ("reason", "notes", "branch__name", "sent_by__email")
    list_filter = ("status", "branch")
    inlines = (BranchWarehouseShipmentLineInline,)
    readonly_fields = (
        "branch",
        "status",
        "sent_by",
        "sent_at",
        "reason",
        "notes",
        "received_by",
        "received_at",
        "receive_reason",
        "cancelled_by",
        "cancelled_at",
        "cancel_reason",
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


@admin.register(BranchWarehouseShipmentChangeLog)
class BranchWarehouseShipmentChangeLogAdmin(admin.ModelAdmin):
    list_display = ("id", "shipment", "action", "user", "created_at")
    readonly_fields = ("shipment", "user", "action", "changes", "reason", "created_at")

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


class DispatchReturnLineInline(admin.TabularInline):
    model = DispatchReturnLine
    extra = 0
    can_delete = False
    readonly_fields = (
        "goods_issue_line",
        "quantity_returned",
        "quantity_restocked",
        "quantity_written_off",
    )

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(DispatchReturn)
class DispatchReturnAdmin(admin.ModelAdmin):
    list_display = ("id", "goods_issue", "branch", "status", "returned_by", "returned_at")
    search_fields = ("return_reason", "branch__name", "goods_issue__id")
    list_filter = ("status", "branch")
    inlines = (DispatchReturnLineInline,)
    readonly_fields = (
        "goods_issue",
        "branch",
        "status",
        "returned_by",
        "returned_at",
        "return_reason",
        "processed_by",
        "processed_at",
        "process_reason",
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


@admin.register(DispatchReturnChangeLog)
class DispatchReturnChangeLogAdmin(admin.ModelAdmin):
    list_display = ("id", "dispatch_return", "action", "user", "created_at")
    readonly_fields = (
        "dispatch_return",
        "user",
        "action",
        "changes",
        "reason",
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


@admin.register(InventoryAlert)
class InventoryAlertAdmin(admin.ModelAdmin):
    list_display = ("id", "kind", "dispatch_return", "branch", "created_at")
    list_filter = ("kind",)
    readonly_fields = ("kind", "dispatch_return", "branch", "payload", "created_at")

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


@admin.register(InventoryAlertReadState)
class InventoryAlertReadStateAdmin(admin.ModelAdmin):
    list_display = ("id", "alert", "user", "read_at")
    readonly_fields = ("alert", "user", "read_at")

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
