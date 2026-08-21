import json
from decimal import Decimal, DecimalException, InvalidOperation

from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.http import JsonResponse
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from accounts.capabilities import can_edit_approval_policy
from accounts.groups import APPROVE_PURCHASE_ORDER
from logging_utils import get_logger

from . import services
from .models import ApprovalLimit, PurchaseOrder
from .permissions import (
    ADD_PO,
    CHANGE_PO,
    procurement_required,
    deny_unless,
)

logger = get_logger("centcompras.procurement")


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
        parsed = Decimal(str(payload[field_name]))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValidationError(f"{field_name} must be a number.") from exc
    if not parsed.is_finite():
        raise ValidationError(f"{field_name} must be a finite number.")
    return parsed


def _parse_int_id(value, field_name):
    """Accept a positive integer id; reject floats/bools that int() would coerce."""
    if isinstance(value, bool) or value is None:
        raise ValidationError(f"{field_name} must be an integer.")
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        raise ValidationError(f"{field_name} must be an integer.")
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped or not stripped.isdigit():
            raise ValidationError(f"{field_name} must be an integer.")
        return int(stripped)
    raise ValidationError(f"{field_name} must be an integer.")


def _serialize_line(line):
    return {
        "id": line.id,
        "item_id": line.item_id,
        "internal_code": line.internal_code,
        "description": line.description,
        "unit_of_measure": line.unit_of_measure,
        "quantity": _dec(line.quantity),
        "unit_cost": _dec(line.unit_cost),
        "discount_commercial": _dec(line.discount_commercial),
        "discount_financial": _dec(line.discount_financial),
        "rappel": _dec(line.rappel),
        "vat_rate": _dec(line.vat_rate),
        "net_unit_cost": _dec(line.net_unit_cost),
        "line_net": _dec(line.line_net),
        "line_vat": _dec(line.line_vat),
        "line_total": _dec(line.line_total),
    }


def _serialize_po(po, include_lines=True):
    payload = {
        "id": po.id,
        "supplier_id": po.supplier_id,
        "supplier_name": po.supplier.name,
        "status": po.status,
        "supplier_ref": po.supplier_ref,
        "notes": po.notes,
        "created_by": po.created_by.email if po.created_by_id else None,
        "approved_by": po.approved_by.email if po.approved_by_id else None,
        "approved_at": po.approved_at.isoformat() if po.approved_at else None,
        "created_at": po.created_at.isoformat(),
        "updated_at": po.updated_at.isoformat(),
    }
    net, vat, gross = po.totals()
    payload["total_net"] = _dec(net)
    payload["total_vat"] = _dec(vat)
    payload["total_gross"] = _dec(gross)
    if include_lines:
        lines = list(po.lines.all())
        payload["lines"] = [_serialize_line(line) for line in lines]
    if po.approved_net is not None:
        payload["approved_net"] = _dec(po.approved_net)
        payload["approved_vat"] = _dec(po.approved_vat)
        payload["approved_gross"] = _dec(po.approved_gross)
    return payload


def _get_po(po_id):
    return (
        PurchaseOrder.objects.select_related(
            "supplier", "created_by", "approved_by"
        )
        .prefetch_related("lines__item")
        .get(pk=po_id)
    )


def _po_response(po):
    return JsonResponse({"purchase_order": _serialize_po(po)})


def _po_error(exc):
    if isinstance(exc, ValidationError):
        message = exc.messages[0] if getattr(exc, "messages", None) else str(exc)
        return _json_error(message, code=getattr(exc, "code", None))
    if isinstance(exc, ObjectDoesNotExist):
        text = str(exc)
        if " matching query does not exist." in text:
            name = text.split(" matching query does not exist.", 1)[0]
            return _json_error(f"{name} not found.", status=404)
        return _json_error(text or "Not found.", status=404)
    if isinstance(exc, (ValueError, TypeError, DecimalException)):
        return _json_error(str(exc))
    raise exc


def _status_action(request, po_id, service_fn, perm):
    denied = deny_unless(request, perm)
    if denied:
        return denied
    try:
        reason = ""
        content_type = request.content_type or ""
        if request.body and "json" in content_type.lower():
            payload = _parse_json(request)
            reason = str(payload.get("reason", ""))
        po = _get_po(po_id)
        po = service_fn(po, request.user, reason=reason)
    except PurchaseOrder.DoesNotExist:
        return _json_error("Purchase order not found.", status=404)
    except ValidationError as exc:
        return _po_error(exc)
    logger.info("%s purchase order id=%s user=%s", service_fn.__name__, po.id, request.user.email)
    return _po_response(po)


@procurement_required
@require_http_methods(["GET", "POST"])
def manage_purchase_order_list(request):
    if request.method == "GET":
        queryset = services.get_purchase_orders()
        return JsonResponse(
            {
                "purchase_orders": [
                    _serialize_po(po, include_lines=False) for po in queryset
                ]
            }
        )

    denied = deny_unless(request, ADD_PO)
    if denied:
        return denied

    try:
        payload = _parse_json(request)
        supplier_id = payload.get("supplier_id")
        if supplier_id is None:
            raise ValidationError("supplier_id is required.")
        po = services.create_purchase_order(
            supplier=_parse_int_id(supplier_id, "supplier_id"),
            user=request.user,
            supplier_ref=str(payload.get("supplier_ref", "")),
            notes=str(payload.get("notes", "")),
        )
    except (ValidationError, ObjectDoesNotExist, ValueError, TypeError) as exc:
        return _po_error(exc)

    logger.info("Console created purchase order id=%s user=%s", po.id, request.user.email)
    return _po_response(po)


@procurement_required
@require_http_methods(["GET", "PATCH"])
def manage_purchase_order_detail(request, po_id):
    try:
        po = _get_po(po_id)
    except PurchaseOrder.DoesNotExist:
        return _json_error("Purchase order not found.", status=404)

    if request.method == "GET":
        return _po_response(po)

    denied = deny_unless(request, CHANGE_PO)
    if denied:
        return denied

    try:
        payload = _parse_json(request)
        fields = {}
        if "supplier_ref" in payload:
            fields["supplier_ref"] = str(payload["supplier_ref"])
        if "notes" in payload:
            fields["notes"] = str(payload["notes"])
        po = services.update_purchase_order(po, user=request.user, **fields)
    except ValidationError as exc:
        return _po_error(exc)

    logger.info("Console updated purchase order id=%s user=%s", po.id, request.user.email)
    return _po_response(po)


@procurement_required
@require_http_methods(["GET", "POST"])
def manage_purchase_order_lines(request, po_id):
    try:
        po = _get_po(po_id)
    except PurchaseOrder.DoesNotExist:
        return _json_error("Purchase order not found.", status=404)

    if request.method == "GET":
        return JsonResponse(
            {"lines": [_serialize_line(line) for line in po.lines.all()]}
        )

    denied = deny_unless(request, CHANGE_PO)
    if denied:
        return denied

    try:
        payload = _parse_json(request)
        item_id = payload.get("item_id")
        if item_id is None:
            raise ValidationError("item_id is required.")
        if "quantity" not in payload:
            raise ValidationError("quantity is required.")
        kwargs = {
            "item": _parse_int_id(item_id, "item_id"),
            "quantity": _parse_decimal(payload, "quantity"),
            "user": request.user,
        }
        if "unit_cost" in payload:
            kwargs["unit_cost"] = _parse_decimal(payload, "unit_cost")
        for field in ("discount_commercial", "discount_financial", "rappel"):
            if field in payload:
                kwargs[field] = _parse_decimal(payload, field)
        services.add_line(po, **kwargs)
    except (ValidationError, ObjectDoesNotExist, ValueError, TypeError, DecimalException) as exc:
        return _po_error(exc)

    po = _get_po(po_id)
    logger.info("Console added line to purchase order id=%s user=%s", po.id, request.user.email)
    return _po_response(po)


@procurement_required
@require_http_methods(["PATCH", "DELETE"])
def manage_purchase_order_line_detail(request, po_id, line_id):
    denied = deny_unless(request, CHANGE_PO)
    if denied:
        return denied

    try:
        po = _get_po(po_id)
        line = po.lines.get(pk=line_id)
    except (PurchaseOrder.DoesNotExist, services.PurchaseOrderLine.DoesNotExist):
        return _json_error("Purchase order line not found.", status=404)

    if request.method == "DELETE":
        try:
            services.remove_line(line, user=request.user)
        except ValidationError as exc:
            return _po_error(exc)
        return JsonResponse({"deleted": True})

    try:
        payload = _parse_json(request)
        fields = {}
        for field in ("quantity", "unit_cost", "discount_commercial", "discount_financial", "rappel"):
            if field in payload:
                fields[field] = _parse_decimal(payload, field)
        services.update_line(line, user=request.user, **fields)
    except ValidationError as exc:
        return _po_error(exc)

    po = _get_po(po_id)
    return _po_response(po)


@procurement_required
@require_POST
def manage_purchase_order_submit(request, po_id):
    return _status_action(request, po_id, services.submit, CHANGE_PO)


@procurement_required
@require_POST
def manage_purchase_order_approve(request, po_id):
    return _status_action(request, po_id, services.approve, APPROVE_PURCHASE_ORDER)


@procurement_required
@require_POST
def manage_purchase_order_reject(request, po_id):
    return _status_action(request, po_id, services.reject, CHANGE_PO)


@procurement_required
@require_POST
def manage_purchase_order_reopen(request, po_id):
    return _status_action(request, po_id, services.reopen, CHANGE_PO)


@procurement_required
@require_POST
def manage_purchase_order_close(request, po_id):
    return _status_action(request, po_id, services.close, CHANGE_PO)


@procurement_required
@require_GET
def manage_purchase_order_history(request, po_id):
    try:
        po = PurchaseOrder.objects.get(pk=po_id)
    except PurchaseOrder.DoesNotExist:
        return _json_error("Purchase order not found.", status=404)

    entries = services.get_purchase_order_history(po)
    return JsonResponse(
        {
            "history": [
                {
                    "id": entry.id,
                    "action": entry.action,
                    "reason": entry.reason,
                    "changes": entry.changes,
                    "user_email": entry.user.email if entry.user_id else "",
                    "created_at": entry.created_at.isoformat(),
                }
                for entry in entries
            ]
        }
    )


def _serialize_approval_limit(limit):
    return {
        "id": limit.id,
        "group_name": limit.group_name,
        "grade": limit.grade,
        "approval_limit": _dec(limit.approval_limit),
        "self_approval_limit": _dec(limit.self_approval_limit),
        "updated_at": limit.updated_at.isoformat(),
    }


@procurement_required
@require_GET
def manage_approval_limit_list(request):
    limits = services.list_approval_limits()
    return JsonResponse(
        {
            "limits": [_serialize_approval_limit(limit) for limit in limits],
            "can_edit": can_edit_approval_policy(request.user),
        }
    )


@procurement_required
@require_http_methods(["PATCH"])
def manage_approval_limit_detail(request, limit_id):
    if not can_edit_approval_policy(request.user):
        return _json_error("Only warehouse admins can change approval limits.", status=403)

    try:
        limit = ApprovalLimit.objects.get(pk=limit_id)
        payload = _parse_json(request)
        fields = {}
        if "approval_limit" in payload:
            fields["approval_limit"] = payload["approval_limit"]
        if "self_approval_limit" in payload:
            fields["self_approval_limit"] = payload["self_approval_limit"]
        limit = services.update_approval_limit(limit, request.user, **fields)
    except ApprovalLimit.DoesNotExist:
        return _json_error("Approval limit not found.", status=404)
    except ValidationError as exc:
        return _po_error(exc)

    return JsonResponse({"limit": _serialize_approval_limit(limit)})
