from decimal import Decimal

from django.conf import settings
from django.db import models

from procurement.models import MONEY_2DP, round_money


class InternalRequestQuerySet(models.QuerySet):
    def for_branch(self, branch):
        return self.filter(branch=branch)

    def for_user_branches(self, user):
        return self.filter(branch__memberships__user=user)


class InternalRequest(models.Model):
    """A branch's Requisição interna against central stock (branch-side)."""

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        SUBMITTED = "submitted", "Submitted"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"
        FULFILLING = "fulfilling", "Fulfilling"
        SHIPPED = "shipped", "Shipped"
        RECEIVED = "received", "Received"
        CLOSED = "closed", "Closed"
        CANCELLED = "cancelled", "Cancelled"

    branch = models.ForeignKey(
        "branches.Branch",
        on_delete=models.PROTECT,
        related_name="internal_requests",
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="internal_requests_created",
    )
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="internal_requests_submitted",
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="internal_requests_approved",
    )
    submitted_at = models.DateTimeField(null=True, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    approved_net = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    approved_vat = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    approved_gross = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    notes = models.TextField(blank=True)
    warehouse_notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = InternalRequestQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"REQ #{self.pk} — {self.branch.name} ({self.status})"

    def totals(self):
        net = sum((line.line_net for line in self.lines.all()), Decimal("0"))
        vat = sum((line.line_vat for line in self.lines.all()), Decimal("0"))
        gross = sum((line.line_total for line in self.lines.all()), Decimal("0"))
        return net, vat, gross


class InternalRequestLine(models.Model):
    internal_request = models.ForeignKey(
        InternalRequest,
        on_delete=models.CASCADE,
        related_name="lines",
    )
    item = models.ForeignKey(
        "products.Item",
        on_delete=models.PROTECT,
        related_name="internal_request_lines",
    )
    description = models.CharField(max_length=255)
    internal_code = models.CharField(max_length=64, blank=True)
    unit_of_measure = models.CharField(max_length=16, blank=True)
    quantity = models.DecimalField(max_digits=12, decimal_places=3)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    vat_rate = models.DecimalField(max_digits=5, decimal_places=4, default=0)
    # Seam (unused in Phase 5): link a restocking PO later (lock 3).
    purchase_order = models.ForeignKey(
        "procurement.PurchaseOrder",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    purchase_order_line = models.ForeignKey(
        "procurement.PurchaseOrderLine",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["id"]
        constraints = [
            models.UniqueConstraint(
                fields=["internal_request", "item"],
                name="unique_request_line_item",
            ),
        ]

    def __str__(self):
        return f"{self.internal_request_id}: {self.description} x {self.quantity}"

    @property
    def line_net(self):
        return round_money(self.unit_price * self.quantity, MONEY_2DP)

    @property
    def line_vat(self):
        return round_money(self.line_net * self.vat_rate, MONEY_2DP)

    @property
    def line_total(self):
        return self.line_net + self.line_vat


class InternalRequestChangeLog(models.Model):
    class Action(models.TextChoices):
        CREATED = "created", "Created"
        STATUS_CHANGED = "status_changed", "Status changed"
        FIELD_UPDATED = "field_updated", "Field updated"
        LINE_ADDED = "line_added", "Line added"
        LINE_UPDATED = "line_updated", "Line updated"
        LINE_REMOVED = "line_removed", "Line removed"

    internal_request = models.ForeignKey(
        InternalRequest,
        on_delete=models.PROTECT,
        related_name="change_logs",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="internal_request_change_logs",
    )
    action = models.CharField(max_length=30, choices=Action.choices)
    changes = models.JSONField(default=dict)
    reason = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.internal_request_id} {self.action} @ {self.created_at:%Y-%m-%d %H:%M}"


class InternalRequestLineChangeLog(models.Model):
    class Action(models.TextChoices):
        CREATED = "created", "Created"
        UPDATED = "updated", "Updated"
        REMOVED = "removed", "Removed"

    internal_request_line = models.ForeignKey(
        InternalRequestLine,
        on_delete=models.CASCADE,
        related_name="change_logs",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="internal_request_line_change_logs",
    )
    action = models.CharField(max_length=30, choices=Action.choices)
    changes = models.JSONField(default=dict)
    reason = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.internal_request_line_id} {self.action} @ {self.created_at:%Y-%m-%d %H:%M}"


class BranchApprovalLimit(models.Model):
    """One global manager cap (self vs others). Branch admin is unlimited (no row)."""

    role = models.CharField(max_length=16, unique=True)
    approval_limit = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        help_text="Max gross (EUR) a manager may approve for another user's request.",
    )
    self_approval_limit = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        help_text="Max gross (EUR) a manager may approve on a request they created.",
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["role"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(approval_limit__gte=0),
                name="branch_approval_limit_gte_zero",
            ),
            models.CheckConstraint(
                condition=models.Q(self_approval_limit__gte=0),
                name="branch_self_approval_limit_gte_zero",
            ),
        ]

    def __str__(self):
        return f"branch {self.role} caps"


class BranchApprovalLimitChangeLog(models.Model):
    class Action(models.TextChoices):
        CREATED = "created", "Created"
        UPDATED = "updated", "Updated"

    branch_approval_limit = models.ForeignKey(
        BranchApprovalLimit,
        on_delete=models.CASCADE,
        related_name="change_logs",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="branch_approval_limit_change_logs",
    )
    action = models.CharField(max_length=30, choices=Action.choices)
    changes = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.branch_approval_limit_id} {self.action} @ {self.created_at:%Y-%m-%d %H:%M}"
