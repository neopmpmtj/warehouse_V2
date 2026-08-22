from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from logging_utils import get_logger

from branches.capabilities import ROLE_ADMIN, ROLE_MANAGER, branch_role
from branches.models import Branch
from procurement.models import MONEY_2DP, round_money
from products.models import Item

from .models import (
    BranchApprovalLimit,
    BranchApprovalLimitChangeLog,
    InternalRequest,
    InternalRequestChangeLog,
    InternalRequestLine,
    InternalRequestLineChangeLog,
)

logger = get_logger("centcompras.orders")

REQUEST_UPDATABLE_FIELDS = ("notes",)
LINE_UPDATABLE_FIELDS = ("quantity",)

STATUS_TRANSITIONS = {
    InternalRequest.Status.DRAFT: {
        InternalRequest.Status.SUBMITTED,
        InternalRequest.Status.CANCELLED,
    },
    InternalRequest.Status.SUBMITTED: {
        InternalRequest.Status.APPROVED,
        InternalRequest.Status.REJECTED,
    },
    InternalRequest.Status.APPROVED: {
        InternalRequest.Status.CANCELLED,
        InternalRequest.Status.FULFILLING,
        InternalRequest.Status.SHIPPED,
        InternalRequest.Status.CLOSED,
    },
    InternalRequest.Status.FULFILLING: {
        InternalRequest.Status.SHIPPED,
    },
    InternalRequest.Status.SHIPPED: {
        InternalRequest.Status.RECEIVED,
        InternalRequest.Status.CLOSED,
    },
    InternalRequest.Status.RECEIVED: {
        InternalRequest.Status.CLOSED,
    },
}

# approved_net/vat/gross are (14,2); keep totals below 1e12 (N9 analogue).
MAX_APPROVED_TOTAL = Decimal("1000000000000")

DEFAULT_BRANCH_APPROVAL_LIMIT = (
    ROLE_MANAGER,
    Decimal("5000.00"),  # approval_limit (others)
    Decimal("100.00"),   # self_approval_limit
)


class InvalidStatusTransitionError(ValidationError):
    def __init__(self, from_status, to_status):
        super().__init__(
            f"Cannot move an internal request from '{from_status}' to '{to_status}'.",
            code="invalid_status_transition",
        )


class RequestNotDraftError(ValidationError):
    def __init__(self):
        super().__init__(
            "Internal request lines can only be changed while the request is a draft.",
            code="request_not_draft",
        )


class InactiveItemError(ValidationError):
    def __init__(self, item=None):
        label = getattr(item, "internal_code", None) or getattr(item, "description", None) or "item"
        super().__init__(f"Cannot use inactive item '{label}'.", code="inactive_item")


class InactiveBranchError(ValidationError):
    def __init__(self, branch=None):
        name = getattr(branch, "name", None) or "branch"
        super().__init__(f"Cannot use inactive branch '{name}'.", code="inactive_branch")


class WholesalePriceMissingError(ValidationError):
    def __init__(self, item=None):
        label = getattr(item, "internal_code", None) or getattr(item, "description", None) or "item"
        super().__init__(
            f"Item '{label}' has no wholesale price.",
            code="wholesale_price_missing",
        )


class DuplicateRequestLineError(ValidationError):
    def __init__(self, item=None):
        label = getattr(item, "internal_code", None) or getattr(item, "description", None) or "item"
        super().__init__(
            f"This request already has a line for '{label}'.",
            code="duplicate_request_line",
        )


class ApprovalDeniedError(ValidationError):
    def __init__(self):
        super().__init__(
            "You do not have permission to approve or cancel this request.",
            code="approval_denied",
        )


class ApproverRequiredError(ValidationError):
    def __init__(self):
        super().__init__("An approver is required.", code="approver_required")


class SelfApprovalLimitError(ValidationError):
    def __init__(self, gross, limit):
        super().__init__(
            f"Self-approval is limited to {limit} EUR gross (this request is {gross}).",
            code="self_approval_limit",
        )


class ApprovalLimitExceededError(ValidationError):
    def __init__(self, gross, limit):
        super().__init__(
            f"Approval is limited to {limit} EUR gross (this request is {gross}).",
            code="approval_limit_exceeded",
        )


class ApprovalLimitMissingError(ValidationError):
    def __init__(self):
        super().__init__(
            "No branch approval limit is configured for managers.",
            code="approval_limit_missing",
        )


class ApprovalPolicyForbiddenError(ValidationError):
    def __init__(self):
        super().__init__(
            "Only warehouse admins can change branch approval limits.",
            code="approval_policy_forbidden",
        )


class ApprovalTotalOverflowError(ValidationError):
    def __init__(self):
        super().__init__(
            "Internal request totals exceed the maximum supported value.",
            code="approval_total_overflow",
        )


class RequestHasGoodsIssueError(ValidationError):
    def __init__(self):
        super().__init__(
            "A request with goods issues cannot be cancelled.",
            code="request_has_goods_issue",
        )


def _resolve_request(request):
    if isinstance(request, InternalRequest):
        return request
    return InternalRequest.objects.get(pk=request)


def _resolve_item(item):
    if isinstance(item, Item):
        return item
    return Item.objects.get(pk=item)


def _lock_request(request):
    return InternalRequest.objects.select_for_update().get(pk=_resolve_request(request).pk)


def _log(request, user, action, changes, reason=""):
    InternalRequestChangeLog.objects.create(
        internal_request=request,
        user=user,
        action=action,
        changes=changes,
        reason=(reason or "").strip(),
    )


def _log_line(line, user, action, changes, reason=""):
    InternalRequestLineChangeLog.objects.create(
        internal_request_line=line,
        user=user,
        action=action,
        changes=changes,
        reason=(reason or "").strip(),
    )


def _ensure_draft(request):
    if request.status != InternalRequest.Status.DRAFT:
        raise RequestNotDraftError()


def _ensure_item_active(item):
    if not Item.objects.filter(
        pk=item.pk, is_active=True, family__is_active=True
    ).exists():
        raise InactiveItemError(item)


def _ensure_branch_active(branch):
    if not Branch.objects.filter(pk=branch.pk, is_active=True).exists():
        raise InactiveBranchError(branch)


def _ensure_wholesale_positive(item):
    if not Item.objects.filter(pk=item.pk, wholesale_price__gt=0).exists():
        raise WholesalePriceMissingError(item)


def _parse_decimal(value, field_name):
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValidationError(f"{field_name} must be a number.", code="invalid_number") from exc
    if not parsed.is_finite():
        raise ValidationError(f"{field_name} must be a finite number.", code="invalid_number")
    return parsed


def _validate_quantity(quantity):
    value = _parse_decimal(quantity, "quantity")
    if value <= 0:
        raise ValidationError("quantity must be greater than zero.", code="invalid_quantity")
    if value >= Decimal("1000000000"):
        raise ValidationError("quantity is too large.", code="invalid_quantity")
    return value


def _require_reason(reason, code, message):
    text = (reason or "").strip()
    if not text:
        raise ValidationError(message, code=code)
    if len(text) > 255:
        raise ValidationError("Reason must be 255 characters or fewer.", code=code)
    return text


def _transition(request, to_status):
    from_status = request.status
    if to_status not in STATUS_TRANSITIONS.get(from_status, set()):
        raise InvalidStatusTransitionError(from_status, to_status)


def ensure_default_branch_approval_limits():
    """Create the global manager cap row if missing. Does not overwrite edits."""
    role, approval, self_approval = DEFAULT_BRANCH_APPROVAL_LIMIT
    BranchApprovalLimit.objects.get_or_create(
        role=role,
        defaults={
            "approval_limit": approval,
            "self_approval_limit": self_approval,
        },
    )


@transaction.atomic
def update_branch_approval_limit(limit, user, approval_limit=None, self_approval_limit=None):
    from accounts.capabilities import can_edit_approval_policy

    if not can_edit_approval_policy(user):
        raise ApprovalPolicyForbiddenError()

    limit = BranchApprovalLimit.objects.select_for_update().get(pk=limit.pk)
    changes = {}
    if approval_limit is not None:
        value = _parse_decimal(approval_limit, "approval_limit")
        if value < 0:
            raise ValidationError("approval_limit must be zero or greater.", code="invalid_approval_limit")
        value = value.quantize(Decimal("0.01"))
        if limit.approval_limit != value:
            changes["approval_limit"] = {"old": str(limit.approval_limit), "new": str(value)}
            limit.approval_limit = value
    if self_approval_limit is not None:
        value = _parse_decimal(self_approval_limit, "self_approval_limit")
        if value < 0:
            raise ValidationError("self_approval_limit must be zero or greater.", code="invalid_approval_limit")
        value = value.quantize(Decimal("0.01"))
        if limit.self_approval_limit != value:
            changes["self_approval_limit"] = {"old": str(limit.self_approval_limit), "new": str(value)}
            limit.self_approval_limit = value
    if not changes:
        return limit
    limit.save(update_fields=[*changes.keys(), "updated_at"])
    BranchApprovalLimitChangeLog.objects.create(
        branch_approval_limit=limit,
        user=user,
        action=BranchApprovalLimitChangeLog.Action.UPDATED,
        changes=changes,
    )
    logger.info(
        "Updated branch approval limit id=%s changes=%s user=%s",
        limit.id,
        list(changes.keys()),
        getattr(user, "email", None),
    )
    return limit


def _assert_can_approve(request, user, gross):
    if user is None or not getattr(user, "pk", None):
        raise ApproverRequiredError()
    role = branch_role(user, request.branch)
    if role == ROLE_ADMIN:
        return
    if role != ROLE_MANAGER:
        raise ApprovalDeniedError()
    ensure_default_branch_approval_limits()
    limit = BranchApprovalLimit.objects.filter(role=ROLE_MANAGER).first()
    if limit is None:
        raise ApprovalLimitMissingError()
    gross = gross.quantize(Decimal("0.01"))
    is_self = user.pk == request.created_by_id
    cap = limit.self_approval_limit if is_self else limit.approval_limit
    if gross > cap:
        if is_self:
            raise SelfApprovalLimitError(gross, cap)
        raise ApprovalLimitExceededError(gross, cap)


@transaction.atomic
def create_internal_request(branch, user, notes=""):
    _ensure_branch_active(branch)
    request = InternalRequest(
        branch=branch,
        created_by=user,
        notes=(notes or "").strip(),
        status=InternalRequest.Status.DRAFT,
    )
    request.full_clean(exclude=None, validate_unique=False, validate_constraints=False)
    request.save()

    _log(
        request,
        user,
        InternalRequestChangeLog.Action.CREATED,
        {
            "branch": {"id": branch.id, "name": branch.name},
            "notes": request.notes,
            "status": request.status,
        },
    )
    logger.info(
        "Created internal request id=%s branch=%s user=%s",
        request.id,
        branch.name,
        getattr(user, "email", None),
    )
    return request


@transaction.atomic
def add_line(request, item, quantity, user=None):
    request = _lock_request(request)
    _ensure_draft(request)
    item = _resolve_item(item)
    _ensure_item_active(item)
    _ensure_wholesale_positive(item)
    quantity = _validate_quantity(quantity)

    if request.lines.filter(item=item).exists():
        raise DuplicateRequestLineError(item)

    line = InternalRequestLine(
        internal_request=request,
        item=item,
        description=item.description,
        internal_code=item.internal_code,
        unit_of_measure=item.unit_of_measure,
        quantity=quantity,
        unit_price=item.wholesale_price,  # snapshot; refreshed at approve
        vat_rate=item.vat_rate.rate,
    )
    try:
        line.full_clean(exclude=None, validate_unique=False, validate_constraints=False)
        line.save()
    except IntegrityError as exc:
        raise DuplicateRequestLineError(item) from exc

    _log(
        request,
        user,
        InternalRequestChangeLog.Action.LINE_ADDED,
        {
            "line_id": line.id,
            "item_id": item.id,
            "description": item.description,
            "internal_code": item.internal_code,
            "quantity": str(quantity),
            "unit_price": str(line.unit_price),
        },
    )
    _log_line(
        line,
        user,
        InternalRequestLineChangeLog.Action.CREATED,
        {"quantity": str(quantity), "unit_price": str(line.unit_price)},
    )
    logger.info(
        "Added line id=%s to request id=%s item=%s user=%s",
        line.id,
        request.id,
        item.internal_code or item.description,
        getattr(user, "email", None),
    )
    return line


@transaction.atomic
def update_line(line, user=None, **fields):
    if not fields:
        return line

    unknown = set(fields) - set(LINE_UPDATABLE_FIELDS)
    if unknown:
        raise ValueError(f"Cannot update fields: {', '.join(sorted(unknown))}")

    request = _lock_request(line.internal_request_id)
    line = InternalRequestLine.objects.select_for_update().get(pk=line.pk)
    _ensure_draft(request)

    changes = {}
    for field_name, new_value in fields.items():
        if field_name == "quantity":
            new_value = _validate_quantity(new_value)
        old_value = getattr(line, field_name)
        if old_value != new_value:
            changes[field_name] = {"old": str(old_value), "new": str(new_value)}
            setattr(line, field_name, new_value)

    if not changes:
        return line

    line.full_clean(exclude=None, validate_unique=False, validate_constraints=False)
    line.save(update_fields=[*changes.keys(), "updated_at"])
    _log(
        request,
        user,
        InternalRequestChangeLog.Action.LINE_UPDATED,
        {"line_id": line.id, **changes},
    )
    _log_line(line, user, InternalRequestLineChangeLog.Action.UPDATED, changes)
    logger.info(
        "Updated line id=%s changes=%s user=%s",
        line.id,
        list(changes.keys()),
        getattr(user, "email", None),
    )
    return line


@transaction.atomic
def remove_line(line, user=None):
    request = _lock_request(line.internal_request_id)
    line = InternalRequestLine.objects.select_for_update().get(pk=line.pk)
    _ensure_draft(request)
    line_id = line.id

    _log(
        request,
        user,
        InternalRequestChangeLog.Action.LINE_REMOVED,
        {
            "line_id": line_id,
            "item_id": line.item_id,
            "description": line.description,
            "quantity": str(line.quantity),
        },
    )
    _log_line(
        line,
        user,
        InternalRequestLineChangeLog.Action.REMOVED,
        {"quantity": str(line.quantity)},
    )
    line.delete()
    logger.info(
        "Removed line id=%s from request id=%s user=%s",
        line_id,
        request.id,
        getattr(user, "email", None),
    )


@transaction.atomic
def update_internal_request(request, user=None, **fields):
    if not fields:
        return request

    unknown = set(fields) - set(REQUEST_UPDATABLE_FIELDS)
    if unknown:
        raise ValueError(f"Cannot update fields: {', '.join(sorted(unknown))}")

    request = InternalRequest.objects.select_for_update().get(pk=request.pk)
    _ensure_draft(request)

    changes = {}
    for field_name, new_value in fields.items():
        new_value = (new_value or "").strip()
        old_value = getattr(request, field_name)
        if old_value != new_value:
            changes[field_name] = {"old": str(old_value), "new": str(new_value)}
            setattr(request, field_name, new_value)

    if not changes:
        return request

    request.save(update_fields=[*changes.keys(), "updated_at"])
    _log(
        request,
        user,
        InternalRequestChangeLog.Action.FIELD_UPDATED,
        changes,
    )
    logger.info(
        "Updated request id=%s changes=%s user=%s",
        request.id,
        list(changes.keys()),
        getattr(user, "email", None),
    )
    return request


@transaction.atomic
def submit(request, user=None):
    request = InternalRequest.objects.select_for_update().get(pk=request.pk)
    if not request.lines.exists():
        raise ValidationError(
            "Cannot submit a request without lines.",
            code="empty_request",
        )
    _ensure_branch_active(request.branch)
    for line in request.lines.select_related("item"):
        _ensure_item_active(line.item)
        _ensure_wholesale_positive(line.item)
    _transition(request, InternalRequest.Status.SUBMITTED)
    request.status = InternalRequest.Status.SUBMITTED
    request.submitted_by = user
    request.submitted_at = timezone.now()
    request.save(update_fields=["status", "submitted_by", "submitted_at", "updated_at"])
    _log(
        request,
        user,
        InternalRequestChangeLog.Action.STATUS_CHANGED,
        {"status": {"old": InternalRequest.Status.DRAFT, "new": InternalRequest.Status.SUBMITTED}},
    )
    logger.info("Submitted request id=%s user=%s", request.id, getattr(user, "email", None))
    return request


@transaction.atomic
def approve(request, user=None, reason=""):
    request = InternalRequest.objects.select_for_update().get(pk=request.pk)
    _transition(request, InternalRequest.Status.APPROVED)
    _ensure_branch_active(request.branch)
    lines = list(request.lines.select_related("item"))
    if not lines:
        raise ValidationError("Cannot approve an empty request.", code="empty_request")
    for line in lines:
        _ensure_item_active(line.item)
        _ensure_wholesale_positive(line.item)

    # Refresh each line's unit_price to the live wholesale (lock 6 / plan §3),
    # then freeze the approved totals.
    for line in lines:
        line.unit_price = line.item.wholesale_price
        line.save(update_fields=["unit_price", "updated_at"])

    net, vat, gross = request.totals()
    _assert_can_approve(request, user, gross)
    for total in (net, vat, gross):
        if total.copy_abs() >= MAX_APPROVED_TOTAL:
            raise ApprovalTotalOverflowError()

    request.status = InternalRequest.Status.APPROVED
    request.approved_by = user
    request.approved_at = timezone.now()
    request.approved_net = round_money(net, MONEY_2DP)
    request.approved_vat = round_money(vat, MONEY_2DP)
    request.approved_gross = round_money(gross, MONEY_2DP)
    request.save(
        update_fields=[
            "status",
            "approved_by",
            "approved_at",
            "approved_net",
            "approved_vat",
            "approved_gross",
            "updated_at",
        ]
    )
    _log(
        request,
        user,
        InternalRequestChangeLog.Action.STATUS_CHANGED,
        {
            "status": {
                "old": InternalRequest.Status.SUBMITTED,
                "new": InternalRequest.Status.APPROVED,
            },
            "approved_net": str(request.approved_net),
            "approved_vat": str(request.approved_vat),
            "approved_gross": str(request.approved_gross),
        },
        reason=reason,
    )
    logger.info("Approved request id=%s user=%s", request.id, getattr(user, "email", None))
    return request


@transaction.atomic
def reject(request, user=None, reason=""):
    request = InternalRequest.objects.select_for_update().get(pk=request.pk)
    reason = _require_reason(
        reason,
        "reject_reason_required",
        "A reason is required to reject a request.",
    )
    _transition(request, InternalRequest.Status.REJECTED)
    request.status = InternalRequest.Status.REJECTED
    request.save(update_fields=["status", "updated_at"])
    _log(
        request,
        user,
        InternalRequestChangeLog.Action.STATUS_CHANGED,
        {"status": {"old": InternalRequest.Status.SUBMITTED, "new": InternalRequest.Status.REJECTED}},
        reason=reason,
    )
    logger.info("Rejected request id=%s user=%s", request.id, getattr(user, "email", None))
    return request


@transaction.atomic
def cancel(request, user=None, reason=""):
    request = InternalRequest.objects.select_for_update().get(pk=request.pk)
    from_status = request.status
    _transition(request, InternalRequest.Status.CANCELLED)

    if from_status == InternalRequest.Status.APPROVED:
        # Only manager / admin may cancel an approved request (lock / §4).
        if branch_role(user, request.branch) not in (ROLE_MANAGER, ROLE_ADMIN):
            raise ApprovalDeniedError()
        reason = _require_reason(
            reason,
            "cancel_reason_required",
            "A reason is required to cancel an approved request.",
        )
        from inventory.models import GoodsIssue

        if GoodsIssue.objects.filter(internal_request=request).exists():
            raise RequestHasGoodsIssueError()

    request.status = InternalRequest.Status.CANCELLED
    request.save(update_fields=["status", "updated_at"])
    _log(
        request,
        user,
        InternalRequestChangeLog.Action.STATUS_CHANGED,
        {"status": {"old": from_status, "new": InternalRequest.Status.CANCELLED}},
        reason=reason,
    )
    logger.info("Cancelled request id=%s user=%s", request.id, getattr(user, "email", None))
    return request


def mark_fulfilling(request, user=None):
    """Transition approved -> fulfilling after a partial issue (called by inventory)."""
    request = InternalRequest.objects.select_for_update().get(pk=request.pk)
    if request.status == InternalRequest.Status.FULFILLING:
        return request
    _transition(request, InternalRequest.Status.FULFILLING)
    old = request.status
    request.status = InternalRequest.Status.FULFILLING
    request.save(update_fields=["status", "updated_at"])
    _log(
        request,
        user,
        InternalRequestChangeLog.Action.STATUS_CHANGED,
        {"status": {"old": old, "new": InternalRequest.Status.FULFILLING}},
    )
    logger.info("Request id=%s now fulfilling user=%s", request.id, getattr(user, "email", None))
    return request


@transaction.atomic
def mark_shipped(request, user=None, reason=""):
    """Transition approved/fulfilling -> shipped (called by inventory)."""
    request = InternalRequest.objects.select_for_update().get(pk=request.pk)
    _transition(request, InternalRequest.Status.SHIPPED)
    old = request.status
    request.status = InternalRequest.Status.SHIPPED
    request.save(update_fields=["status", "updated_at"])
    _log(
        request,
        user,
        InternalRequestChangeLog.Action.STATUS_CHANGED,
        {"status": {"old": old, "new": InternalRequest.Status.SHIPPED}},
        reason=reason,
    )
    logger.info("Request id=%s shipped user=%s", request.id, getattr(user, "email", None))
    return request


@transaction.atomic
def mark_received(request, user=None):
    """Transition shipped -> received after the first branch receipt (called by inventory)."""
    request = InternalRequest.objects.select_for_update().get(pk=request.pk)
    if request.status == InternalRequest.Status.RECEIVED:
        return request
    _transition(request, InternalRequest.Status.RECEIVED)
    old = request.status
    request.status = InternalRequest.Status.RECEIVED
    request.save(update_fields=["status", "updated_at"])
    _log(
        request,
        user,
        InternalRequestChangeLog.Action.STATUS_CHANGED,
        {"status": {"old": old, "new": InternalRequest.Status.RECEIVED}},
    )
    logger.info("Request id=%s now received user=%s", request.id, getattr(user, "email", None))
    return request


@transaction.atomic
def mark_closed(request, user=None, reason=""):
    """Transition shipped/received -> closed (called by inventory)."""
    request = InternalRequest.objects.select_for_update().get(pk=request.pk)
    _transition(request, InternalRequest.Status.CLOSED)
    old = request.status
    request.status = InternalRequest.Status.CLOSED
    request.save(update_fields=["status", "updated_at"])
    _log(
        request,
        user,
        InternalRequestChangeLog.Action.STATUS_CHANGED,
        {"status": {"old": old, "new": InternalRequest.Status.CLOSED}},
        reason=reason,
    )
    logger.info("Request id=%s closed user=%s", request.id, getattr(user, "email", None))
    return request


def get_internal_requests(branch=None, status=None):
    queryset = (
        InternalRequest.objects.select_related("branch", "created_by", "approved_by")
        .prefetch_related("lines")
    )
    if branch is not None:
        queryset = queryset.for_branch(branch)
    if status is not None:
        queryset = queryset.filter(status=status)
    return queryset


def get_request_history(request):
    return request.change_logs.select_related("user").order_by("-created_at")
