from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Sum

from logging_utils import get_logger

from products.models import Item

from procurement.models import (
    PurchaseOrder,
    PurchaseOrderChangeLog,
    PurchaseOrderLine,
)

from .models import (
    BranchItemStock,
    BranchReceipt,
    BranchReceiptLine,
    BranchStockMovement,
    GoodsIssue,
    GoodsIssueLine,
    GoodsReceipt,
    GoodsReceiptLine,
    StockMovement,
)
from orders.models import InternalRequest, InternalRequestLine

logger = get_logger("centcompras.inventory")


class PurchaseOrderNotReceivableError(ValidationError):
    def __init__(self, status):
        super().__init__(
            f"Cannot receive goods against a purchase order with status '{status}'.",
            code="purchase_order_not_receivable",
        )


class InvalidReceivedQuantityError(ValidationError):
    def __init__(self, message):
        super().__init__(message, code="invalid_received_quantity")


class PurchaseOrderLineNotFoundError(ValidationError):
    def __init__(self):
        super().__init__(
            "Purchase order line not found on this purchase order.",
            code="purchase_order_line_not_found",
        )


class NoLinesToReceiveError(ValidationError):
    def __init__(self):
        super().__init__("No lines to receive.", code="no_lines_to_receive")


class InvalidAdjustmentQuantityError(ValidationError):
    def __init__(self):
        super().__init__(
            "Adjustment quantity must be non-zero.",
            code="invalid_adjustment_quantity",
        )


class InvalidQuantityError(ValidationError):
    def __init__(self, message="Quantity must be a finite number."):
        super().__init__(message, code="invalid_quantity")


class InvalidReceiptLineError(ValidationError):
    def __init__(self, message="Each receipt line must be a valid object with line_id and quantity_received."):
        super().__init__(message, code="invalid_receipt_line")


class DuplicateReceiptLineError(ValidationError):
    def __init__(self):
        super().__init__(
            "A purchase order line was provided more than once in this receipt.",
            code="duplicate_receipt_line",
        )


class NegativeStockError(ValidationError):
    def __init__(self):
        super().__init__(
            "Stock cannot be adjusted below zero.",
            code="negative_stock",
        )


def _resolve_po(po):
    if isinstance(po, PurchaseOrder):
        return po
    return PurchaseOrder.objects.get(pk=po)


def _resolve_item(item):
    if isinstance(item, Item):
        return item
    return Item.objects.get(pk=item)


def _received_qty_map(po):
    """Map PO line id → total received, in a single grouped aggregate query."""
    totals = (
        GoodsReceiptLine.objects.filter(purchase_order_line__purchase_order=po)
        .values("purchase_order_line_id")
        .annotate(total=Sum("quantity_received"))
    )
    return {
        row["purchase_order_line_id"]: (row["total"] or Decimal("0"))
        for row in totals
    }


def ledger_quantity(item):
    """Sum of StockMovement.quantity for an item (source of truth for Item.quantity)."""
    item = _resolve_item(item)
    total = StockMovement.objects.filter(item=item).aggregate(total=Sum("quantity"))[
        "total"
    ]
    if total is None:
        return Decimal("0.000")
    return total.quantize(Decimal("0.001"))


def _parse_decimal_quantity(value):
    """Parse, bound and quantise a quantity to the field precision (12,3), rounding half away from zero."""
    try:
        qty = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise InvalidQuantityError() from exc
    if not qty.is_finite():
        raise InvalidQuantityError()
    rounded = qty.quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)
    if qty != 0 and rounded == 0:
        raise InvalidQuantityError("Quantity is too small (rounds to zero).")
    if rounded.copy_abs() >= Decimal("1000000000"):
        raise InvalidQuantityError("Quantity is too large.")
    return rounded


def _validate_received_qty(value):
    qty = _parse_decimal_quantity(value)
    if qty <= 0:
        raise InvalidReceivedQuantityError(
            "quantity_received must be greater than zero."
        )
    return qty


def _is_fully_received(po):
    received_map = _received_qty_map(po)
    return all(
        (line.quantity - received_map.get(line.id, Decimal("0"))) <= 0
        for line in po.lines.all()
    )


def _log_goods_received(po, user, changes):
    PurchaseOrderChangeLog.objects.create(
        purchase_order=po,
        user=user,
        action=PurchaseOrderChangeLog.Action.GOODS_RECEIVED,
        changes=changes,
    )


def _write_movement(item, quantity, movement_type, user, content_object=None, reason=""):
    item = Item.objects.select_for_update().get(pk=item.pk)
    new_quantity = (item.quantity or Decimal("0")) + quantity
    if quantity < 0 and new_quantity < 0:
        raise NegativeStockError()
    if new_quantity.copy_abs() >= Decimal("1000000000"):
        raise InvalidQuantityError(
            "Resulting stock balance is too large for the quantity field."
        )
    kwargs = {
        "item": item,
        "quantity": quantity,
        "movement_type": movement_type,
        "created_by": user,
        "reason": (reason or "").strip(),
    }
    if content_object is not None:
        kwargs["content_type"] = ContentType.objects.get_for_model(content_object)
        kwargs["object_id"] = content_object.pk
    movement = StockMovement.objects.create(**kwargs)

    item.quantity = new_quantity.quantize(Decimal("0.001"))
    item.save(update_fields=["quantity", "updated_at"])
    return movement


@transaction.atomic
def receive_goods(po, lines, user, reference="", notes=""):
    """Record goods received against an approved/received PO and write stock."""
    po = PurchaseOrder.objects.select_for_update().get(pk=_resolve_po(po).pk)

    if po.status not in (
        PurchaseOrder.Status.APPROVED,
        PurchaseOrder.Status.RECEIVED,
    ):
        raise PurchaseOrderNotReceivableError(po.status)

    normalized = []
    seen_line_ids = set()
    received_map = _received_qty_map(po)
    for entry in lines:
        if not isinstance(entry, dict):
            raise InvalidReceiptLineError()
        line_id = entry.get("line_id", entry.get("purchase_order_line_id"))
        if line_id is None:
            raise InvalidReceiptLineError(
                "Each receipt line requires a line_id."
            )
        if "quantity_received" not in entry:
            raise InvalidReceiptLineError(
                "Each receipt line requires quantity_received."
            )
        qty = _validate_received_qty(entry["quantity_received"])
        try:
            po_line = po.lines.get(pk=line_id)
        except PurchaseOrderLine.DoesNotExist:
            raise PurchaseOrderLineNotFoundError()
        if po_line.id in seen_line_ids:
            raise DuplicateReceiptLineError()
        seen_line_ids.add(po_line.id)
        remaining = po_line.quantity - received_map.get(po_line.id, Decimal("0"))
        if qty > remaining:
            raise InvalidReceivedQuantityError(
                f"Received quantity {qty} exceeds remaining {remaining} "
                f"for PO line {po_line.id}."
            )
        normalized.append((po_line, qty))

    if not normalized:
        raise NoLinesToReceiveError()

    # Lock items in pk order so concurrent multi-item receipts cannot deadlock.
    item_ids = sorted({po_line.item_id for po_line, _qty in normalized})
    list(
        Item.objects.filter(pk__in=item_ids)
        .order_by("pk")
        .select_for_update()
    )

    receipt = GoodsReceipt.objects.create(
        purchase_order=po,
        received_by=user,
        reference=(reference or "").strip(),
        notes=(notes or "").strip(),
    )

    for po_line, qty in normalized:
        GoodsReceiptLine.objects.create(
            goods_receipt=receipt,
            purchase_order_line=po_line,
            quantity_received=qty,
        )
        _write_movement(
            po_line.item,
            qty,
            StockMovement.Type.RECEIPT,
            user,
            content_object=receipt,
        )

    _log_goods_received(
        po,
        user,
        {
            "receipt_id": receipt.id,
            "reference": receipt.reference,
            "lines": [
                {
                    "line_id": po_line.id,
                    "item_id": po_line.item_id,
                    "quantity_received": str(qty),
                }
                for po_line, qty in normalized
            ],
        },
    )

    if po.status == PurchaseOrder.Status.APPROVED:
        from procurement.services import receive

        po = receive(po, user, reason="Goods received")
    if _is_fully_received(po):
        from procurement.services import close

        close(po, user, reason="Fully received")

    logger.info(
        "Received goods receipt id=%s po=%s lines=%s user=%s",
        receipt.id,
        po.id,
        len(normalized),
        getattr(user, "email", None),
    )
    return receipt


@transaction.atomic
def adjust_stock(item, quantity, reason, user):
    """Manual stock adjustment (warehouse admin only)."""
    item = _resolve_item(item)
    quantity = _parse_decimal_quantity(quantity)
    if quantity == 0:
        raise InvalidAdjustmentQuantityError()

    reason = (reason or "").strip()
    if not reason:
        raise ValidationError(
            "A reason is required to adjust stock.",
            code="adjust_reason_required",
        )

    movement = _write_movement(
        item,
        quantity,
        StockMovement.Type.ADJUSTMENT,
        user,
        reason=reason,
    )

    logger.info(
        "Adjusted stock item=%s quantity=%s user=%s",
        item.id,
        str(quantity),
        getattr(user, "email", None),
    )
    return movement


def get_goods_receipts(po=None):
    queryset = GoodsReceipt.objects.select_related(
        "purchase_order__supplier",
        "received_by",
    ).prefetch_related("lines__purchase_order_line__item")
    if po is not None:
        queryset = queryset.filter(purchase_order=po)
    return queryset


def get_stock_movements(item=None):
    queryset = StockMovement.objects.select_related("item", "created_by", "content_type")
    if item is not None:
        queryset = queryset.filter(item=item)
    return queryset


def get_receipt_summary(po):
    """Per-line ordered / received / remaining for a purchase order."""
    po = _resolve_po(po)
    lines = list(po.lines.select_related("item").all())
    received_map = _received_qty_map(po)
    return [
        {
            "line_id": line.id,
            "item_id": line.item_id,
            "internal_code": line.internal_code,
            "description": line.description,
            "unit_of_measure": line.unit_of_measure,
            "quantity": str(line.quantity),
            "received": str(received_map.get(line.id, Decimal("0"))),
            "remaining": str(line.quantity - received_map.get(line.id, Decimal("0"))),
        }
        for line in lines
    ]


class RequestNotIssuableError(ValidationError):
    def __init__(self, status):
        super().__init__(
            f"Cannot issue goods against a request with status '{status}'.",
            code="request_not_issuable",
        )


class RequestLineNotFoundError(ValidationError):
    def __init__(self):
        super().__init__(
            "Request line not found on this request.",
            code="request_line_not_found",
        )


class InvalidIssuedQuantityError(ValidationError):
    def __init__(self, message="Issued quantity must be a positive number."):
        super().__init__(message, code="invalid_issued_quantity")


class NoLinesToIssueError(ValidationError):
    def __init__(self):
        super().__init__("No lines to issue.", code="no_lines_to_issue")


class InvalidIssueLineError(ValidationError):
    def __init__(self, message="Each issue line must be a valid object with line_id and quantity_issued."):
        super().__init__(message, code="invalid_issue_line")


class DuplicateIssueLineError(ValidationError):
    def __init__(self):
        super().__init__(
            "A request line was provided more than once in this issue.",
            code="duplicate_issue_line",
        )


class InsufficientStockError(ValidationError):
    def __init__(self, item, on_hand, requested):
        label = getattr(item, "internal_code", None) or getattr(item, "description", None) or item.pk
        super().__init__(
            f"Insufficient stock for '{label}': {requested} requested, {on_hand} on hand.",
            code="insufficient_stock",
        )


def _resolve_request(request):
    if isinstance(request, InternalRequest):
        return request
    return InternalRequest.objects.get(pk=request)


def _issued_qty_map(request):
    """Map request line id -> total quantity already issued, in one grouped query."""
    totals = (
        GoodsIssueLine.objects.filter(internal_request_line__internal_request=request)
        .values("internal_request_line_id")
        .annotate(total=Sum("quantity_issued"))
    )
    return {
        row["internal_request_line_id"]: (row["total"] or Decimal("0"))
        for row in totals
    }


def _is_fully_issued(request):
    issued_map = _issued_qty_map(request)
    return all(
        (line.quantity - issued_map.get(line.id, Decimal("0"))) <= 0
        for line in request.lines.all()
    )


def _validate_issued_qty(value):
    qty = _parse_decimal_quantity(value)
    if qty <= 0:
        raise InvalidIssuedQuantityError()
    return qty


@transaction.atomic
def issue_goods(request, lines, user, reference="", notes=""):
    """Issue goods to a branch against an approved/fulfilling request (partial OK)."""
    from orders.services import mark_fulfilling, mark_shipped

    request = InternalRequest.objects.select_for_update().get(pk=_resolve_request(request).pk)

    if request.status not in (
        InternalRequest.Status.APPROVED,
        InternalRequest.Status.FULFILLING,
    ):
        raise RequestNotIssuableError(request.status)

    normalized = []
    seen_line_ids = set()
    issued_map = _issued_qty_map(request)
    for entry in lines:
        if not isinstance(entry, dict):
            raise InvalidIssueLineError()
        line_id = entry.get("line_id", entry.get("internal_request_line_id"))
        if line_id is None:
            raise InvalidIssueLineError("Each issue line requires a line_id.")
        if "quantity_issued" not in entry:
            raise InvalidIssueLineError("Each issue line requires quantity_issued.")
        qty = _validate_issued_qty(entry["quantity_issued"])
        try:
            request_line = request.lines.get(pk=line_id)
        except InternalRequestLine.DoesNotExist:
            raise RequestLineNotFoundError()
        if request_line.id in seen_line_ids:
            raise DuplicateIssueLineError()
        seen_line_ids.add(request_line.id)
        remaining = request_line.quantity - issued_map.get(request_line.id, Decimal("0"))
        if qty > remaining:
            raise InvalidIssuedQuantityError(
                f"Issued quantity {qty} exceeds remaining {remaining} "
                f"for request line {request_line.id}."
            )
        normalized.append((request_line, qty))

    if not normalized:
        raise NoLinesToIssueError()

    # Lock items in pk order (M6) so concurrent issues cannot deadlock.
    item_ids = sorted({request_line.item_id for request_line, _qty in normalized})
    items = {
        item.id: item
        for item in Item.objects.filter(pk__in=item_ids).order_by("pk").select_for_update()
    }

    for request_line, qty in normalized:
        on_hand = items[request_line.item_id].quantity
        if qty > on_hand:
            raise InsufficientStockError(request_line.item, on_hand, qty)

    goods_issue = GoodsIssue.objects.create(
        internal_request=request,
        issued_by=user,
        reference=(reference or "").strip(),
        notes=(notes or "").strip(),
    )

    for request_line, qty in normalized:
        GoodsIssueLine.objects.create(
            goods_issue=goods_issue,
            internal_request_line=request_line,
            quantity_issued=qty,
        )
        _write_movement(
            request_line.item,
            -qty,
            StockMovement.Type.GOODS_ISSUE,
            user,
            content_object=goods_issue,
        )

    if _is_fully_issued(request):
        mark_shipped(request, user)
    else:
        mark_fulfilling(request, user)

    logger.info(
        "Issued goods gi=%s request=%s lines=%s user=%s",
        goods_issue.id,
        request.id,
        len(normalized),
        getattr(user, "email", None),
    )
    return goods_issue


@transaction.atomic
def short_close_issue(request, user, reason=""):
    """Warehouse short-close: write off the unshipped remainder and mark shipped."""
    from orders.services import mark_shipped

    request = InternalRequest.objects.select_for_update().get(pk=_resolve_request(request).pk)
    if request.status not in (
        InternalRequest.Status.APPROVED,
        InternalRequest.Status.FULFILLING,
    ):
        raise RequestNotIssuableError(request.status)

    reason = (reason or "").strip()
    if not reason:
        raise ValidationError(
            "A reason is required to short-close a request.",
            code="short_close_reason_required",
        )

    request = mark_shipped(request, user, reason=reason)
    logger.info(
        "Short-closed request id=%s user=%s",
        request.id,
        getattr(user, "email", None),
    )
    return request


def get_issue_summary(request):
    """Per-line ordered / issued / remaining / on-hand for a request (warehouse queue)."""
    request = _resolve_request(request)
    lines = list(request.lines.select_related("item").all())
    issued_map = _issued_qty_map(request)
    return [
        {
            "line_id": line.id,
            "item_id": line.item_id,
            "internal_code": line.internal_code,
            "description": line.description,
            "unit_of_measure": line.unit_of_measure,
            "quantity": str(line.quantity),
            "issued": str(issued_map.get(line.id, Decimal("0"))),
            "remaining": str(line.quantity - issued_map.get(line.id, Decimal("0"))),
            "on_hand": str(line.item.quantity),
        }
        for line in lines
    ]


class BranchReceiptNotAllowedError(ValidationError):
    def __init__(self, status):
        super().__init__(
            f"Cannot receive against a request with status '{status}'.",
            code="branch_receipt_not_allowed",
        )


class BranchIssueLineNotFoundError(ValidationError):
    def __init__(self):
        super().__init__(
            "Goods issue line not found on this dispatch.",
            code="branch_issue_line_not_found",
        )


class InvalidBranchReceivedQuantityError(ValidationError):
    def __init__(self, message="Received quantity must be a positive number."):
        super().__init__(message, code="invalid_branch_received_quantity")


class NoBranchLinesToReceiveError(ValidationError):
    def __init__(self):
        super().__init__("No lines to receive.", code="no_branch_lines_to_receive")


class DuplicateBranchReceiptLineError(ValidationError):
    def __init__(self):
        super().__init__(
            "A goods issue line was provided more than once in this receipt.",
            code="duplicate_branch_receipt_line",
        )


class BranchInsufficientShippedError(ValidationError):
    def __init__(self, remaining, received):
        super().__init__(
            f"Received quantity {received} exceeds shipped remaining {remaining}.",
            code="branch_insufficient_shipped",
        )


class BranchAdjustmentForbiddenError(ValidationError):
    def __init__(self):
        super().__init__(
            "Only branch admins can adjust branch stock.",
            code="branch_adjustment_forbidden",
        )


class BranchStockNegativeError(ValidationError):
    def __init__(self):
        super().__init__(
            "Branch stock cannot be adjusted below zero.",
            code="branch_stock_negative",
        )


def _resolve_goods_issue(goods_issue):
    if isinstance(goods_issue, GoodsIssue):
        return goods_issue
    return GoodsIssue.objects.get(pk=goods_issue)


def _branch_received_qty_map(goods_issue):
    totals = (
        BranchReceiptLine.objects.filter(goods_issue_line__goods_issue=goods_issue)
        .values("goods_issue_line_id")
        .annotate(total=Sum("quantity_received"))
    )
    return {
        row["goods_issue_line_id"]: (row["total"] or Decimal("0"))
        for row in totals
    }


def _request_received_qty_map(request):
    totals = (
        BranchReceiptLine.objects.filter(
            goods_issue_line__goods_issue__internal_request=request
        )
        .values("goods_issue_line__internal_request_line_id")
        .annotate(total=Sum("quantity_received"))
    )
    return {
        row["goods_issue_line__internal_request_line_id"]: (row["total"] or Decimal("0"))
        for row in totals
    }


def _is_request_fully_received(request):
    issued_map = _issued_qty_map(request)
    received_map = _request_received_qty_map(request)
    return all(
        (issued_map.get(line.id, Decimal("0")) - received_map.get(line.id, Decimal("0"))) <= 0
        for line in request.lines.all()
    )


def _validate_branch_received_qty(value):
    qty = _parse_decimal_quantity(value)
    if qty <= 0:
        raise InvalidBranchReceivedQuantityError()
    return qty


def _write_branch_movement(branch, item, quantity, movement_type, user, content_object=None, reason=""):
    stock, _ = BranchItemStock.objects.get_or_create(branch=branch, item=item)
    stock = BranchItemStock.objects.select_for_update().get(pk=stock.pk)
    new_quantity = (stock.quantity or Decimal("0")) + quantity
    if new_quantity < 0:
        raise BranchStockNegativeError()

    kwargs = {
        "branch": branch,
        "item": item,
        "quantity": quantity,
        "movement_type": movement_type,
        "created_by": user,
        "reason": (reason or "").strip(),
    }
    if content_object is not None:
        kwargs["content_type"] = ContentType.objects.get_for_model(content_object)
        kwargs["object_id"] = content_object.pk
    movement = BranchStockMovement.objects.create(**kwargs)

    stock.quantity = new_quantity.quantize(Decimal("0.001"))
    stock.save(update_fields=["quantity", "updated_at"])
    return movement


@transaction.atomic
def receive_at_branch(goods_issue, lines, user, reference="", notes=""):
    """Confirm branch receipt against a dispatch (guia); reject over-receipt."""
    from orders.services import mark_closed, mark_received

    goods_issue = GoodsIssue.objects.select_for_update().get(
        pk=_resolve_goods_issue(goods_issue).pk
    )
    request = InternalRequest.objects.select_for_update().get(
        pk=goods_issue.internal_request_id
    )

    if request.status not in (
        InternalRequest.Status.SHIPPED,
        InternalRequest.Status.RECEIVED,
    ):
        raise BranchReceiptNotAllowedError(request.status)

    normalized = []
    seen_line_ids = set()
    received_map = _branch_received_qty_map(goods_issue)
    for entry in lines:
        if not isinstance(entry, dict):
            raise ValidationError(
                "Each receipt line must be an object with line_id and quantity_received.",
                code="invalid_branch_receipt_line",
            )
        line_id = entry.get("line_id", entry.get("goods_issue_line_id"))
        if line_id is None:
            raise ValidationError("Each receipt line requires a line_id.", code="invalid_branch_receipt_line")
        if "quantity_received" not in entry:
            raise ValidationError("Each receipt line requires quantity_received.", code="invalid_branch_receipt_line")
        qty = _validate_branch_received_qty(entry["quantity_received"])
        try:
            issue_line = goods_issue.lines.get(pk=line_id)
        except GoodsIssueLine.DoesNotExist:
            raise BranchIssueLineNotFoundError()
        if issue_line.id in seen_line_ids:
            raise DuplicateBranchReceiptLineError()
        seen_line_ids.add(issue_line.id)
        remaining = issue_line.quantity_issued - received_map.get(issue_line.id, Decimal("0"))
        if qty > remaining:
            raise BranchInsufficientShippedError(remaining, qty)
        normalized.append((issue_line, qty))

    if not normalized:
        raise NoBranchLinesToReceiveError()

    branch = request.branch
    item_ids = sorted({issue_line.internal_request_line.item_id for issue_line, _qty in normalized})
    for item_id in item_ids:
        stock, _ = BranchItemStock.objects.get_or_create(branch=branch, item_id=item_id)
        BranchItemStock.objects.select_for_update().get(pk=stock.pk)

    receipt = BranchReceipt.objects.create(
        goods_issue=goods_issue,
        received_by=user,
        reference=(reference or "").strip(),
        notes=(notes or "").strip(),
    )

    for issue_line, qty in normalized:
        BranchReceiptLine.objects.create(
            branch_receipt=receipt,
            goods_issue_line=issue_line,
            quantity_received=qty,
        )
        _write_branch_movement(
            branch,
            issue_line.internal_request_line.item,
            qty,
            BranchStockMovement.Type.RECEIPT,
            user,
            content_object=receipt,
        )

    if _is_request_fully_received(request):
        mark_closed(request, user)
    else:
        mark_received(request, user)

    logger.info(
        "Branch receipt br=%s gi=%s lines=%s user=%s",
        receipt.id,
        goods_issue.id,
        len(normalized),
        getattr(user, "email", None),
    )
    return receipt


@transaction.atomic
def short_close_receipt(request, user, reason=""):
    """Branch short-close: write off the unreceived remainder and mark closed."""
    from orders.services import mark_closed

    request = InternalRequest.objects.select_for_update().get(pk=_resolve_request(request).pk)
    if request.status not in (
        InternalRequest.Status.SHIPPED,
        InternalRequest.Status.RECEIVED,
    ):
        raise BranchReceiptNotAllowedError(request.status)

    reason = (reason or "").strip()
    if not reason:
        raise ValidationError(
            "A reason is required to short-close a request.",
            code="short_close_reason_required",
        )

    request = mark_closed(request, user, reason=reason)
    logger.info(
        "Branch short-closed request id=%s user=%s",
        request.id,
        getattr(user, "email", None),
    )
    return request


@transaction.atomic
def adjust_branch_stock(branch, item, quantity, reason, user):
    """Manual branch stock adjustment (branch admin only, reason required)."""
    from branches.capabilities import ROLE_ADMIN, branch_role

    if branch_role(user, branch) != ROLE_ADMIN:
        raise BranchAdjustmentForbiddenError()

    item = _resolve_item(item)
    quantity = _parse_decimal_quantity(quantity)
    if quantity == 0:
        raise InvalidAdjustmentQuantityError()

    reason = (reason or "").strip()
    if not reason:
        raise ValidationError(
            "A reason is required to adjust branch stock.",
            code="branch_adjust_reason_required",
        )

    movement = _write_branch_movement(
        branch,
        item,
        quantity,
        BranchStockMovement.Type.ADJUSTMENT,
        user,
        reason=reason,
    )
    logger.info(
        "Adjusted branch stock branch=%s item=%s quantity=%s user=%s",
        branch.id,
        item.id,
        str(quantity),
        getattr(user, "email", None),
    )
    return movement


def get_branch_goods_issues(branch):
    """Dispatches awaiting/partially received by a branch (shipped/received requests)."""
    return (
        GoodsIssue.objects.filter(
            internal_request__branch=branch,
            internal_request__status__in=[
                InternalRequest.Status.SHIPPED,
                InternalRequest.Status.RECEIVED,
            ],
        )
        .select_related("internal_request", "issued_by")
        .prefetch_related("lines__internal_request_line__item")
        .order_by("-issued_at")
    )


def get_branch_issue_summary(goods_issue):
    """Per-line shipped / received / remaining for a branch dispatch (guia)."""
    goods_issue = _resolve_goods_issue(goods_issue)
    lines = list(goods_issue.lines.select_related("internal_request_line__item").all())
    received_map = _branch_received_qty_map(goods_issue)
    return [
        {
            "line_id": line.id,
            "item_id": line.internal_request_line.item_id,
            "internal_code": line.internal_request_line.internal_code,
            "description": line.internal_request_line.description,
            "unit_of_measure": line.internal_request_line.unit_of_measure,
            "quantity_issued": str(line.quantity_issued),
            "received": str(received_map.get(line.id, Decimal("0"))),
            "remaining": str(line.quantity_issued - received_map.get(line.id, Decimal("0"))),
        }
        for line in lines
    ]
