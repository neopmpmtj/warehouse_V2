import json
from decimal import DecimalException

from django.core.exceptions import ValidationError
from django.http import Http404, JsonResponse
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from logging_utils import get_logger

from accounts.capabilities import can_edit_approval_policy, can_short_close_issue
from branches.capabilities import can_approve_request
from branches.permissions import active_branch_required
from inventory.services import get_issue_summary, issue_goods, short_close_issue

from .models import BranchApprovalLimit, InternalRequest, InternalRequestLine
from .permissions import ISSUE_GOODS, deny_unless, internal_request_queue_required
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
    update_branch_approval_limit,
    update_internal_request,
    update_line,
)

logger = get_logger("centcompras.orders")


def _json_error(message, status=400, code=None):
    payload = {"error": message}
    if code:
        payload["code"] = code
    return JsonResponse(payload, status=status)


def _validation_error_response(exc, status=400):
    if isinstance(exc, ValidationError):
        message = exc.messages[0] if getattr(exc, "messages", None) else str(exc)
        return _json_error(message, status=status, code=getattr(exc, "code", None))
    return _json_error(str(exc), status=status, code=getattr(exc, "code", None))


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
        return _validation_error_response(exc)
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
        return _validation_error_response(exc)
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
        return _validation_error_response(exc)
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
        return _validation_error_response(exc)
    return JsonResponse({"line": _serialize_line(line)})


@active_branch_required
@require_http_methods(["DELETE"])
def request_remove_line(request, request_id, line_id):
    req = _get_request_or_404(request_id, request.active_branch)
    line = _get_line_or_404(req, line_id)
    try:
        remove_line(line, request.user)
    except ValidationError as exc:
        return _validation_error_response(exc)
    return JsonResponse({"ok": True})


@active_branch_required
@require_POST
def request_submit(request, request_id):
    req = _get_request_or_404(request_id, request.active_branch)
    try:
        req = submit(req, request.user)
    except ValidationError as exc:
        return _validation_error_response(exc)
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
        return _validation_error_response(exc)
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
        return _validation_error_response(exc)
    return JsonResponse({"request": _serialize_request(req)})


@active_branch_required
@require_POST
def request_cancel(request, request_id):
    req = _get_request_or_404(request_id, request.active_branch)
    data = _parse_body(request)
    try:
        req = cancel(req, request.user, reason=data.get("reason", ""))
    except ValidationError as exc:
        return _validation_error_response(exc)
    return JsonResponse({"request": _serialize_request(req)})


@active_branch_required
@require_GET
def request_history(request, request_id):
    req = _get_request_or_404(request_id, request.active_branch)
    return JsonResponse(
        {"history": [_serialize_history(log) for log in get_request_history(req)]}
    )


def _parse_int_id(value, field_name):
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


def _serialize_warehouse_request(request):
    return {
        "id": request.id,
        "branch_id": request.branch_id,
        "branch_name": request.branch.name,
        "status": request.status,
        "notes": request.notes,
        "warehouse_notes": request.warehouse_notes,
        "created_by": request.created_by.email if request.created_by_id else None,
        "approved_gross": _decimal_string(request.approved_gross) if request.approved_gross is not None else None,
        "created_at": request.created_at.isoformat(),
        "submitted_at": request.submitted_at.isoformat() if request.submitted_at else None,
        "approved_at": request.approved_at.isoformat() if request.approved_at else None,
        "lines": get_issue_summary(request),
    }


def _serialize_branch_approval_limit(limit):
    return {
        "id": limit.id,
        "role": limit.role,
        "approval_limit": _decimal_string(limit.approval_limit),
        "self_approval_limit": _decimal_string(limit.self_approval_limit),
        "updated_at": limit.updated_at.isoformat(),
    }


@internal_request_queue_required
@require_GET
def warehouse_request_list(request):
    branch_id = request.GET.get("branch_id")
    queryset = (
        InternalRequest.objects.select_related("branch", "created_by")
        .prefetch_related("lines__item")
        .filter(
            status__in=[
                InternalRequest.Status.APPROVED,
                InternalRequest.Status.FULFILLING,
            ]
        )
    )
    if branch_id:
        try:
            branch_id = _parse_int_id(branch_id, "branch_id")
        except ValidationError:
            return _json_error("Invalid branch_id.", status=400)
        queryset = queryset.for_branch(branch_id)
    return JsonResponse(
        {"requests": [_serialize_warehouse_request(r) for r in queryset]}
    )


@internal_request_queue_required
@require_GET
def warehouse_request_detail(request, request_id):
    try:
        req = (
            InternalRequest.objects.select_related("branch", "created_by")
            .prefetch_related("lines__item")
            .get(pk=request_id)
        )
    except InternalRequest.DoesNotExist:
        return _json_error("Internal request not found.", status=404)
    return JsonResponse({"request": _serialize_warehouse_request(req)})


@internal_request_queue_required
@require_POST
def warehouse_request_issue(request, request_id):
    denied = deny_unless(request, ISSUE_GOODS)
    if denied:
        return denied
    try:
        data = _parse_body(request)
        lines = data.get("lines")
        if not isinstance(lines, list) or not lines:
            raise ValidationError("lines must be a non-empty list.")
        goods_issue = issue_goods(
            request_id,
            lines,
            request.user,
            reference=str(data.get("reference", "")),
            notes=str(data.get("notes", "")),
        )
    except ValidationError as exc:
        return _validation_error_response(exc)
    return JsonResponse({"goods_issue_id": goods_issue.id}, status=201)


@internal_request_queue_required
@require_POST
def warehouse_request_short_close(request, request_id):
    if not can_short_close_issue(request.user):
        return _json_error(
            "Short-close requires manager grade 2+ or admin.",
            status=403,
            code="short_close_denied",
        )
    try:
        data = _parse_body(request)
        req = short_close_issue(request_id, request.user, reason=str(data.get("reason", "")))
    except ValidationError as exc:
        return _validation_error_response(exc)
    return JsonResponse({"request": _serialize_warehouse_request(req)})


@internal_request_queue_required
@require_http_methods(["GET", "PATCH"])
def branch_approval_limit_list(request):
    if request.method == "GET":
        limits = BranchApprovalLimit.objects.all()
        return JsonResponse(
            {"branch_approval_limits": [_serialize_branch_approval_limit(l) for l in limits]}
        )

    if not can_edit_approval_policy(request.user):
        return _json_error(
            "Only warehouse admins can change branch approval limits.",
            status=403,
            code="approval_policy_forbidden",
        )
    data = _parse_body(request)
    try:
        limit_id = data.get("id")
        if limit_id is not None:
            limit = BranchApprovalLimit.objects.get(pk=limit_id)
        else:
            limit = BranchApprovalLimit.objects.first()
        limit = update_branch_approval_limit(
            limit,
            request.user,
            approval_limit=data.get("approval_limit"),
            self_approval_limit=data.get("self_approval_limit"),
        )
    except (ValidationError, BranchApprovalLimit.DoesNotExist) as exc:
        return _validation_error_response(exc)
    return JsonResponse({"branch_approval_limit": _serialize_branch_approval_limit(limit)})
