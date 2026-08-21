from decimal import Decimal

from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models


class GoodsReceipt(models.Model):
    """A delivery received against an approved purchase order (partial allowed)."""

    purchase_order = models.ForeignKey(
        "procurement.PurchaseOrder",
        on_delete=models.PROTECT,
        related_name="goods_receipts",
    )
    received_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="goods_receipts",
    )
    received_at = models.DateTimeField(auto_now_add=True)
    reference = models.CharField(max_length=255, blank=True)
    notes = models.TextField(blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-received_at"]

    def __str__(self):
        return f"GR #{self.pk} — PO #{self.purchase_order_id}"

    def total_received(self):
        return sum(
            (line.quantity_received for line in self.lines.all()),
            Decimal("0"),
        )


class GoodsReceiptLine(models.Model):
    goods_receipt = models.ForeignKey(
        GoodsReceipt,
        on_delete=models.CASCADE,
        related_name="lines",
    )
    purchase_order_line = models.ForeignKey(
        "procurement.PurchaseOrderLine",
        on_delete=models.PROTECT,
        related_name="goods_receipt_lines",
    )
    quantity_received = models.DecimalField(max_digits=12, decimal_places=3)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["id"]
        constraints = [
            models.UniqueConstraint(
                fields=["goods_receipt", "purchase_order_line"],
                name="unique_goods_receipt_line",
            ),
        ]

    def __str__(self):
        return (
            f"GR #{self.goods_receipt_id}: "
            f"PO line {self.purchase_order_line_id} x {self.quantity_received}"
        )


class StockMovement(models.Model):
    """Append-only stock ledger. `Item.quantity` is the cached sum of these."""

    class Type(models.TextChoices):
        RECEIPT = "receipt", "Receipt"
        GOODS_ISSUE = "goods_issue", "Goods issue"
        ADJUSTMENT = "adjustment", "Adjustment"

    item = models.ForeignKey(
        "products.Item",
        on_delete=models.PROTECT,
        related_name="stock_movements",
    )
    quantity = models.DecimalField(
        max_digits=12,
        decimal_places=3,
        help_text="Signed quantity: positive in, negative out.",
    )
    movement_type = models.CharField(max_length=20, choices=Type.choices)
    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="stock_movements",
    )
    object_id = models.PositiveIntegerField(null=True, blank=True)
    content_object = GenericForeignKey("content_type", "object_id")
    reason = models.CharField(max_length=255, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="stock_movements",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        permissions = [
            ("can_adjust_stock", "Can manually adjust stock"),
        ]
        indexes = [
            models.Index(fields=["item", "-created_at"]),
        ]
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(content_type__isnull=True, object_id__isnull=True)
                    | models.Q(content_type__isnull=False, object_id__isnull=False)
                ),
                name="stockmovement_reference_both_or_neither",
            ),
        ]

    def __str__(self):
        return f"{self.movement_type} {self.item_id} {self.quantity:+}"


class GoodsIssue(models.Model):
    """A dispatch of goods from the central warehouse to a branch (guia)."""

    internal_request = models.ForeignKey(
        "orders.InternalRequest",
        on_delete=models.PROTECT,
        related_name="goods_issues",
    )
    issued_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="goods_issues",
    )
    issued_at = models.DateTimeField(auto_now_add=True)
    reference = models.CharField(max_length=255, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-issued_at"]
        permissions = [
            ("can_issue_goods", "Can issue goods to branches"),
        ]

    def __str__(self):
        return f"GI #{self.pk} — REQ #{self.internal_request_id}"


class GoodsIssueLine(models.Model):
    goods_issue = models.ForeignKey(
        GoodsIssue,
        on_delete=models.CASCADE,
        related_name="lines",
    )
    internal_request_line = models.ForeignKey(
        "orders.InternalRequestLine",
        on_delete=models.PROTECT,
        related_name="goods_issue_lines",
    )
    quantity_issued = models.DecimalField(max_digits=12, decimal_places=3)

    class Meta:
        ordering = ["id"]
        constraints = [
            models.UniqueConstraint(
                fields=["goods_issue", "internal_request_line"],
                name="unique_goods_issue_line",
            ),
        ]

    def __str__(self):
        return (
            f"GI #{self.goods_issue_id}: REQ line {self.internal_request_line_id} "
            f"x {self.quantity_issued}"
        )


class BranchReceipt(models.Model):
    """A branch's confirmation of goods received against a dispatch (guia)."""

    goods_issue = models.ForeignKey(
        GoodsIssue,
        on_delete=models.PROTECT,
        related_name="branch_receipts",
    )
    received_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="branch_receipts",
    )
    received_at = models.DateTimeField(auto_now_add=True)
    reference = models.CharField(max_length=255, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-received_at"]

    def __str__(self):
        return f"BR #{self.pk} — GI #{self.goods_issue_id}"


class BranchReceiptLine(models.Model):
    branch_receipt = models.ForeignKey(
        BranchReceipt,
        on_delete=models.CASCADE,
        related_name="lines",
    )
    goods_issue_line = models.ForeignKey(
        GoodsIssueLine,
        on_delete=models.PROTECT,
        related_name="branch_receipt_lines",
    )
    quantity_received = models.DecimalField(max_digits=12, decimal_places=3)

    class Meta:
        ordering = ["id"]
        constraints = [
            models.UniqueConstraint(
                fields=["branch_receipt", "goods_issue_line"],
                name="unique_branch_receipt_line",
            ),
        ]

    def __str__(self):
        return (
            f"BR #{self.branch_receipt_id}: GI line {self.goods_issue_line_id} "
            f"x {self.quantity_received}"
        )


class BranchItemStock(models.Model):
    """Cached branch stock balance per (branch, item), written only via BranchStockMovement."""

    branch = models.ForeignKey(
        "branches.Branch",
        on_delete=models.PROTECT,
        related_name="item_stock",
    )
    item = models.ForeignKey(
        "products.Item",
        on_delete=models.PROTECT,
        related_name="branch_stock",
    )
    quantity = models.DecimalField(max_digits=12, decimal_places=3, default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["branch", "item"]
        constraints = [
            models.UniqueConstraint(
                fields=["branch", "item"],
                name="unique_branch_item_stock",
            ),
            models.CheckConstraint(
                condition=models.Q(quantity__gte=0),
                name="branch_item_stock_gte_zero",
            ),
        ]

    def __str__(self):
        return f"{self.branch.name} / {self.item_id}: {self.quantity}"


class BranchStockMovement(models.Model):
    """Append-only branch stock ledger. BranchItemStock.quantity is its cached sum."""

    class Type(models.TextChoices):
        RECEIPT = "receipt", "Receipt"
        ADJUSTMENT = "adjustment", "Adjustment"

    branch = models.ForeignKey(
        "branches.Branch",
        on_delete=models.PROTECT,
        related_name="stock_movements",
    )
    item = models.ForeignKey(
        "products.Item",
        on_delete=models.PROTECT,
        related_name="branch_stock_movements",
    )
    quantity = models.DecimalField(
        max_digits=12,
        decimal_places=3,
        help_text="Signed quantity: positive in, negative out.",
    )
    movement_type = models.CharField(max_length=20, choices=Type.choices)
    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="branch_stock_movements",
    )
    object_id = models.PositiveIntegerField(null=True, blank=True)
    content_object = GenericForeignKey("content_type", "object_id")
    reason = models.CharField(max_length=255, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="branch_stock_movements",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["branch", "item", "-created_at"]),
        ]
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(content_type__isnull=True, object_id__isnull=True)
                    | models.Q(content_type__isnull=False, object_id__isnull=False)
                ),
                name="branchstockmovement_reference_both_or_neither",
            ),
        ]

    def __str__(self):
        return f"{self.branch_id}/{self.item_id} {self.movement_type} {self.quantity:+}"
