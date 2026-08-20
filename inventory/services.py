from decimal import Decimal

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

from .models import GoodsReceipt, GoodsReceiptLine, StockMovement

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


def _resolve_po(po):
    if isinstance(po, PurchaseOrder):
        return po
    return PurchaseOrder.objects.get(pk=po)


def _resolve_item(item):
    if isinstance(item, Item):
        return item
    return Item.objects.get(pk=item)


def _received_qty(po_line):
    total = GoodsReceiptLine.objects.filter(purchase_order_line=po_line).aggregate(
        total=Sum("quantity_received")
    )["total"]
    return total or Decimal("0")


def remaining_qty(po_line):
    return po_line.quantity - _received_qty(po_line)


def _validate_received_qty(value):
    qty = Decimal(str(value))
    if qty <= 0:
        raise InvalidReceivedQuantityError(
            "quantity_received must be greater than zero."
        )
    return qty


def _is_fully_received(po):
    return all(remaining_qty(line) <= 0 for line in po.lines.all())


def _log_goods_received(po, user, changes):
    PurchaseOrderChangeLog.objects.create(
        purchase_order=po,
        user=user,
        action=PurchaseOrderChangeLog.Action.GOODS_RECEIVED,
        changes=changes,
    )


def _write_movement(item, quantity, movement_type, user, content_object=None, reason=""):
    item = Item.objects.select_for_update().get(pk=item.pk)
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
    StockMovement.objects.create(**kwargs)

    item.quantity = (item.quantity or Decimal("0")) + quantity
    item.save(update_fields=["quantity", "updated_at"])
    return item


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
    for entry in lines:
        line_id = entry.get("line_id", entry.get("purchase_order_line_id"))
        qty = _validate_received_qty(entry["quantity_received"])
        try:
            po_line = po.lines.get(pk=line_id)
        except PurchaseOrderLine.DoesNotExist:
            raise PurchaseOrderLineNotFoundError()
        remaining = remaining_qty(po_line)
        if qty > remaining:
            raise InvalidReceivedQuantityError(
                f"Received quantity {qty} exceeds remaining {remaining} "
                f"for PO line {po_line.id}."
            )
        normalized.append((po_line, qty))

    if not normalized:
        raise NoLinesToReceiveError()

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

        po = receive(po, user)
    if _is_fully_received(po):
        from procurement.services import close

        close(po, user)

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
    quantity = Decimal(str(quantity))
    if quantity == 0:
        raise InvalidAdjustmentQuantityError()

    updated = _write_movement(
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
    return updated


def get_goods_receipts(po=None):
    queryset = GoodsReceipt.objects.select_related(
        "purchase_order__supplier",
        "received_by",
    ).prefetch_related("lines__purchase_order_line__item")
    if po is not None:
        queryset = queryset.filter(purchase_order=po)
    return queryset


def get_stock_movements(item=None):
    queryset = StockMovement.objects.select_related("item", "created_by")
    if item is not None:
        queryset = queryset.filter(item=item)
    return queryset


def get_receipt_summary(po):
    """Per-line ordered / received / remaining for a purchase order."""
    po = _resolve_po(po)
    lines = po.lines.select_related("item").all()
    return [
        {
            "line_id": line.id,
            "item_id": line.item_id,
            "internal_code": line.internal_code,
            "description": line.description,
            "unit_of_measure": line.unit_of_measure,
            "quantity": str(line.quantity),
            "received": str(_received_qty(line)),
            "remaining": str(remaining_qty(line)),
        }
        for line in lines
    ]
