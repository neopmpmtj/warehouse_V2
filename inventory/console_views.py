import json
from decimal import Decimal, DecimalException, InvalidOperation

from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.http import JsonResponse
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from logging_utils import get_logger

from . import services
from .models import GoodsReceipt, StockMovement
from .permissions import (
    ADD_GOODS_RECEIPT,
    ADJUST_STOCK,
    deny_unless,
    inventory_required,
)

logger = get_logger("centcompras.inventory")


def _json_error(message, status=400, code=None):
    payload = {"error": message}
    if code:
        payload["code"] = code
    return JsonResponse(payload, status=status)


def _parse_json(request):
    try:
        payload = json.loads(request.body.decode() or "{}")
    except json.JSONDecodeError:
        raise ValidationError("Request body must be valid JSON.")
    if not isinstance(payload, dict):
        raise ValidationError("Request body must be a JSON object.")
    return payload


def _dec(value):
    return str(value)


def _parse_decimal(payload, field_name, required=True):
    if field_name not in payload:
        if required:
            raise ValidationError(f"{field_name} is required.")
        return None
    try:
        return Decimal(str(payload[field_name]))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValidationError(f"{field_name} must be a number.") from exc


def _serialize_receipt_line(line):
    po_line = line.purchase_order_line
    return {
        "id": line.id,
        "purchase_order_line_id": po_line.id,
        "item_id": po_line.item_id,
        "internal_code": po_line.internal_code,
        "description": po_line.description,
        "unit_of_measure": po_line.unit_of_measure,
        "quantity_received": _dec(line.quantity_received),
    }


def _serialize_receipt(receipt, include_lines=True):
    payload = {
        "id": receipt.id,
        "purchase_order_id": receipt.purchase_order_id,
        "supplier_id": receipt.purchase_order.supplier_id,
        "supplier_name": receipt.purchase_order.supplier.name,
        "received_by": receipt.received_by.email if receipt.received_by_id else None,
        "received_at": receipt.received_at.isoformat(),
        "reference": receipt.reference,
        "notes": receipt.notes,
        "total_received": _dec(receipt.total_received()),
    }
    if include_lines:
        payload["lines"] = [
            _serialize_receipt_line(line) for line in receipt.lines.all()
        ]
    return payload


def _serialize_movement(movement, receipt=None):
    if receipt is not None:
        reference = f"GR #{receipt.id}"
        if receipt.reference:
            reference += f" — {receipt.reference}"
    elif movement.content_type_id is not None:
        reference = f"{movement.content_type.model} #{movement.object_id}"
    else:
        reference = ""
    return {
        "id": movement.id,
        "item_id": movement.item_id,
        "internal_code": movement.item.internal_code,
        "description": movement.item.description,
        "quantity": _dec(movement.quantity),
        "movement_type": movement.movement_type,
        "reference": reference,
        "reason": movement.reason,
        "created_by": movement.created_by.email if movement.created_by_id else None,
        "created_at": movement.created_at.isoformat(),
    }


def _inv_error(exc):
    if isinstance(exc, ValidationError):
        message = exc.messages[0] if getattr(exc, "messages", None) else str(exc)
        return _json_error(message, code=getattr(exc, "code", None))
    if isinstance(exc, (ObjectDoesNotExist, ValueError, TypeError, DecimalException)):
        return _json_error(str(exc))
    raise exc


def _get_receipt(receipt_id):
    return (
        GoodsReceipt.objects.select_related(
            "purchase_order__supplier",
            "received_by",
        )
        .prefetch_related("lines__purchase_order_line")
        .get(pk=receipt_id)
    )


@inventory_required
@require_http_methods(["GET", "POST"])
def manage_goods_receipt_list(request):
    if request.method == "GET":
        receipts = services.get_goods_receipts()
        return JsonResponse(
            {
                "goods_receipts": [
                    _serialize_receipt(receipt, include_lines=False)
                    for receipt in receipts
                ]
            }
        )

    denied = deny_unless(request, ADD_GOODS_RECEIPT)
    if denied:
        return denied

    try:
        payload = _parse_json(request)
        purchase_order_id = payload.get("purchase_order_id")
        if purchase_order_id is None:
            raise ValidationError("purchase_order_id is required.")
        lines = payload.get("lines")
        if not isinstance(lines, list) or not lines:
            raise ValidationError("lines must be a non-empty list.")
        receipt = services.receive_goods(
            po=purchase_order_id,
            lines=lines,
            user=request.user,
            reference=str(payload.get("reference", "")),
            notes=str(payload.get("notes", "")),
        )
    except (ValidationError, ObjectDoesNotExist, ValueError, TypeError, DecimalException) as exc:
        return _inv_error(exc)

    logger.info(
        "Console created goods receipt id=%s user=%s", receipt.id, request.user.email
    )
    return JsonResponse(
        {"goods_receipt": _serialize_receipt(_get_receipt(receipt.id))}
    )


@inventory_required
@require_GET
def manage_goods_receipt_detail(request, receipt_id):
    try:
        receipt = _get_receipt(receipt_id)
    except GoodsReceipt.DoesNotExist:
        return _json_error("Goods receipt not found.", status=404)
    return JsonResponse({"goods_receipt": _serialize_receipt(receipt)})


@inventory_required
@require_GET
def manage_receipt_summary(request, po_id):
    from procurement.models import PurchaseOrder

    try:
        po = PurchaseOrder.objects.get(pk=po_id)
    except PurchaseOrder.DoesNotExist:
        return _json_error("Purchase order not found.", status=404)
    return JsonResponse({"lines": services.get_receipt_summary(po)})


@inventory_required
@require_GET
def manage_stock_movements(request):
    item_id = request.GET.get("item_id")
    try:
        movements = list(services.get_stock_movements(item=item_id))
    except ValueError:
        return _json_error("Invalid item_id.", status=400)
    receipt_ct = ContentType.objects.get_for_model(GoodsReceipt)
    receipt_ids = [
        m.object_id
        for m in movements
        if m.content_type_id == receipt_ct.id and m.object_id
    ]
    receipts = {r.id: r for r in GoodsReceipt.objects.filter(pk__in=receipt_ids)}
    return JsonResponse(
        {
            "stock_movements": [
                _serialize_movement(
                    m,
                    receipt=receipts.get(m.object_id)
                    if m.content_type_id == receipt_ct.id
                    else None,
                )
                for m in movements
            ]
        }
    )


@inventory_required
@require_POST
def manage_stock_adjustment(request):
    denied = deny_unless(request, ADJUST_STOCK)
    if denied:
        return denied

    try:
        payload = _parse_json(request)
        item_id = payload.get("item_id")
        if item_id is None:
            raise ValidationError("item_id is required.")
        if "quantity" not in payload:
            raise ValidationError("quantity is required.")
        movement = services.adjust_stock(
            item=item_id,
            quantity=_parse_decimal(payload, "quantity"),
            reason=str(payload.get("reason", "")),
            user=request.user,
        )
    except (ValidationError, ObjectDoesNotExist, ValueError, TypeError, DecimalException) as exc:
        return _inv_error(exc)

    logger.info(
        "Console adjusted stock item=%s user=%s", movement.item_id, request.user.email
    )
    return JsonResponse(
        {
            "item_id": movement.item_id,
            "quantity": _dec(movement.quantity),
            "balance": _dec(movement.item.quantity),
        }
    )
