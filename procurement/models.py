from decimal import Decimal

from django.conf import settings
from django.db import models


class PurchaseOrder(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        SUBMITTED = "submitted", "Submitted"
        APPROVED = "approved", "Approved"
        RECEIVED = "received", "Received"
        CLOSED = "closed", "Closed"
        REJECTED = "rejected", "Rejected"

    supplier = models.ForeignKey(
        "products.Supplier",
        on_delete=models.PROTECT,
        related_name="purchase_orders",
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="purchase_orders_created",
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="purchase_orders_approved",
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    approved_net = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    approved_vat = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    approved_gross = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    supplier_ref = models.CharField(max_length=255, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        permissions = [
            ("can_approve", "Can approve purchase orders"),
        ]

    def __str__(self):
        return f"PO #{self.pk} — {self.supplier.name} ({self.status})"

    def totals(self):
        net = sum((line.line_net for line in self.lines.all()), Decimal("0"))
        vat = sum((line.line_vat for line in self.lines.all()), Decimal("0"))
        gross = sum((line.line_total for line in self.lines.all()), Decimal("0"))
        return net, vat, gross


class PurchaseOrderLine(models.Model):
    purchase_order = models.ForeignKey(
        PurchaseOrder,
        on_delete=models.CASCADE,
        related_name="lines",
    )
    item = models.ForeignKey(
        "products.Item",
        on_delete=models.PROTECT,
        related_name="purchase_order_lines",
    )
    description = models.CharField(max_length=255)
    internal_code = models.CharField(max_length=64, blank=True)
    unit_of_measure = models.CharField(max_length=16, blank=True)
    quantity = models.DecimalField(max_digits=12, decimal_places=3, default=0)
    unit_cost = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    discount_commercial = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    discount_financial = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    rappel = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    vat_rate = models.DecimalField(max_digits=5, decimal_places=4, default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return f"{self.purchase_order_id}: {self.description} x {self.quantity}"

    @property
    def total_discount_rate(self):
        return self.discount_commercial + self.discount_financial + self.rappel

    @property
    def net_unit_cost(self):
        value = self.unit_cost * (Decimal("1") - self.total_discount_rate / Decimal("100"))
        return value.quantize(Decimal("0.0001"))

    @property
    def line_net(self):
        return (self.net_unit_cost * self.quantity).quantize(Decimal("0.01"))

    @property
    def line_vat(self):
        return (self.line_net * self.vat_rate).quantize(Decimal("0.01"))

    @property
    def line_total(self):
        return self.line_net + self.line_vat


class PurchaseOrderChangeLog(models.Model):
    class Action(models.TextChoices):
        CREATED = "created", "Created"
        STATUS_CHANGED = "status_changed", "Status changed"
        FIELD_UPDATED = "field_updated", "Field updated"
        LINE_ADDED = "line_added", "Line added"
        LINE_UPDATED = "line_updated", "Line updated"
        LINE_REMOVED = "line_removed", "Line removed"
        GOODS_RECEIVED = "goods_received", "Goods received"

    purchase_order = models.ForeignKey(
        PurchaseOrder,
        on_delete=models.PROTECT,
        related_name="change_logs",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="purchase_order_change_logs",
    )
    action = models.CharField(max_length=30, choices=Action.choices)
    changes = models.JSONField(default=dict)
    reason = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.purchase_order_id} {self.action} @ {self.created_at:%Y-%m-%d %H:%M}"
