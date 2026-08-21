import json
from decimal import DecimalException

from django.core.exceptions import ValidationError
from django.http import Http404, JsonResponse
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from logging_utils import get_logger

from branches.capabilities import can_approve_request
from branches.permissions import active_branch_required

from .models import InternalRequest, InternalRequestLine
from .services import (
    add_line,
    approve,
    cancel,
    create_internal_request,
    get_internal_requests,
    get_request_history,
    reject,
    remove_line,
    submit,
    update_internal_request,
    update_line,
)

logger = get_logger("centcompras.orders")


def _json_error(message, status=400, code=None):
    payload = {"error": message}
    if code:
        payload["code"] = code
    return JsonResponse(payload, status=status)


def _decimal_string(value):
    return str(value)


def _serialize_line(line):
    return {
        "id": line.id,
        "item_id": line.item_id,
        "description": line.description,
        "internal_code": line.internal_code,
        "unit_of_measure": line.unit_of_measure,
        "quantity": _decimal_string(line.quantity),
        "unit_price": _decimal_string(line.unit_price),
        "vat_rate": _decimal_string(line.vat_rate),
    }


def _serialize_request(request):
    net, vat, gross = request.totals()
    return {
        "id": request.id,
        "branch_id": request.branch_id,
        "status": request.status,
        "notes": request.notes,
        "warehouse_notes": request.warehouse_notes,
        "created_by": request.created_by_id,
        "approved_net": _decimal_string(request.approved_net) if request.approved_net is not None else None,
        "approved_vat": _decimal_string(request.approved_vat) if request.approved_vat is not None else None,
        "approved_gross": _decimal_string(request.approved_gross) if request.approved_gross is not None else None,
        "totals": {
            "net": _decimal_string(net),
            "vat": _decimal_string(vat),
            "gross": _decimal_string(gross),
        },
        "created_at": request.created_at.isoformat(),
        "lines": [_serialize_line(line) for line in request.lines.all()],
    }


def _serialize_history(log):
    return {
        "id": log.id,
        "user": log.user.email if log.user else None,
        "action": log.action,
        "changes": log.changes,
        "reason": log.reason,
        "created_at": log.created_at.isoformat(),
    }


def _parse_body(request):
    try:
        return json.loads(request.body or b"{}")
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise ValidationError("Request body must be valid JSON.", code="invalid_json")


def _get_request_or_404(request_id, branch):
    """Branch isolation: other-branch requests are 404, not 403."""
    try:
        return (
            InternalRequest.objects.prefetch_related("lines")
            .get(pk=request_id, branch=branch)
        )
    except InternalRequest.DoesNotExist:
        raise Http404("Internal request not found.")


def _get_line_or_404(request, line_id):
    try:
        return request.lines.get(pk=line_id)
    except InternalRequestLine.DoesNotExist:
        raise Http404("Line not found.")


@active_branch_required
@require_GET
def request_list(request):
    queryset = get_internal_requests(branch=request.active_branch)
    return JsonResponse(
        {"requests": [_serialize_request(r) for r in queryset]}
    )


@active_branch_required
@require_POST
def request_create(request):
    branch = request.active_branch
    data = _parse_body(request)
    try:
        req = create_internal_request(branch, request.user, notes=data.get("notes", ""))
    except ValidationError as exc:
        return _json_error(str(exc), status=400, code=getattr(exc, "code", None))
    return JsonResponse({"request": _serialize_request(req)}, status=201)


@active_branch_required
@require_GET
def request_detail(request, request_id):
    req = _get_request_or_404(request_id, request.active_branch)
    return JsonResponse({"request": _serialize_request(req)})


@active_branch_required
@require_http_methods(["PATCH"])
def request_update(request, request_id):
    req = _get_request_or_404(request_id, request.active_branch)
    data = _parse_body(request)
    try:
        req = update_internal_request(req, request.user, notes=data.get("notes"))
    except ValidationError as exc:
        return _json_error(str(exc), status=400, code=getattr(exc, "code", None))
    return JsonResponse({"request": _serialize_request(req)})


@active_branch_required
@require_POST
def request_add_line(request, request_id):
    req = _get_request_or_404(request_id, request.active_branch)
    data = _parse_body(request)
    try:
        line = add_line(
            req,
            item=data.get("item_id"),
            quantity=data.get("quantity"),
            user=request.user,
        )
    except ValidationError as exc:
        return _json_error(str(exc), status=400, code=getattr(exc, "code", None))
    return JsonResponse({"line": _serialize_line(line)}, status=201)


@active_branch_required
@require_http_methods(["PATCH"])
def request_update_line(request, request_id, line_id):
    req = _get_request_or_404(request_id, request.active_branch)
    line = _get_line_or_404(req, line_id)
    data = _parse_body(request)
    try:
        line = update_line(line, request.user, quantity=data.get("quantity"))
    except ValidationError as exc:
        return _json_error(str(exc), status=400, code=getattr(exc, "code", None))
    return JsonResponse({"line": _serialize_line(line)})


@active_branch_required
@require_http_methods(["DELETE"])
def request_remove_line(request, request_id, line_id):
    req = _get_request_or_404(request_id, request.active_branch)
    line = _get_line_or_404(req, line_id)
    try:
        remove_line(line, request.user)
    except ValidationError as exc:
        return _json_error(str(exc), status=400, code=getattr(exc, "code", None))
    return JsonResponse({"ok": True})


@active_branch_required
@require_POST
def request_submit(request, request_id):
    req = _get_request_or_404(request_id, request.active_branch)
    try:
        req = submit(req, request.user)
    except ValidationError as exc:
        return _json_error(str(exc), status=400, code=getattr(exc, "code", None))
    return JsonResponse({"request": _serialize_request(req)})


@active_branch_required
@require_POST
def request_approve(request, request_id):
    if not can_approve_request(request.user, request.active_branch):
        return _json_error("Approval is restricted to managers and admins.", status=403, code="approval_denied")
    req = _get_request_or_404(request_id, request.active_branch)
    data = _parse_body(request)
    try:
        req = approve(req, request.user, reason=data.get("reason", ""))
    except ValidationError as exc:
        return _json_error(str(exc), status=400, code=getattr(exc, "code", None))
    return JsonResponse({"request": _serialize_request(req)})


@active_branch_required
@require_POST
def request_reject(request, request_id):
    if not can_approve_request(request.user, request.active_branch):
        return _json_error("Rejection is restricted to managers and admins.", status=403, code="approval_denied")
    req = _get_request_or_404(request_id, request.active_branch)
    data = _parse_body(request)
    try:
        req = reject(req, request.user, reason=data.get("reason", ""))
    except ValidationError as exc:
        return _json_error(str(exc), status=400, code=getattr(exc, "code", None))
    return JsonResponse({"request": _serialize_request(req)})


@active_branch_required
@require_POST
def request_cancel(request, request_id):
    req = _get_request_or_404(request_id, request.active_branch)
    data = _parse_body(request)
    try:
        req = cancel(req, request.user, reason=data.get("reason", ""))
    except ValidationError as exc:
        return _json_error(str(exc), status=400, code=getattr(exc, "code", None))
    return JsonResponse({"request": _serialize_request(req)})


@active_branch_required
@require_GET
def request_history(request, request_id):
    req = _get_request_or_404(request_id, request.active_branch)
    return JsonResponse(
        {"history": [_serialize_history(log) for log in get_request_history(req)]}
    )
