import json

from django.core.exceptions import ValidationError
from django.db import models
from django.http import Http404, JsonResponse
from django.views.decorators.http import require_GET, require_POST

from logging_utils import get_logger

from branches.permissions import active_branch_required
from products.models import Item

from .capabilities import can_force_close_thread, is_warehouse_staff
from .models import ItemRequestThread, ThreadMessage
from .permissions import warehouse_threads_required
from .services import (
    close_thread,
    create_thread,
    get_thread_history,
    get_thread_messages,
    link_items,
    mark_read,
    post_message,
)

logger = get_logger("centcompras.threads")


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


def _parse_json(request):
    try:
        payload = json.loads(request.body or b"{}")
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise ValidationError("Request body must be valid JSON.", code="invalid_json")
    if not isinstance(payload, dict):
        raise ValidationError("Request body must be a JSON object.", code="invalid_json")
    return payload


def _get_thread_or_404(thread_id, branch=None):
    """Branch isolation: other-branch threads are 404, not 403."""
    try:
        queryset = ItemRequestThread.objects.prefetch_related("read_states")
        if branch is not None:
            queryset = queryset.filter(branch=branch)
        return queryset.get(pk=thread_id)
    except ItemRequestThread.DoesNotExist:
        raise Http404("Request thread not found.")


def _serialize_item(item):
    return {
        "id": item.id,
        "internal_code": item.internal_code,
        "description": item.description,
    }


def _serialize_thread(thread, user):
    return {
        "id": thread.id,
        "branch_id": thread.branch_id,
        "branch_name": thread.branch.name,
        "branch_active": thread.branch.is_active,
        "subject": thread.subject,
        "status": thread.status,
        "opened_by_id": thread.opened_by_id,
        "opened_by_email": thread.opened_by.email,
        "last_activity_at": thread.last_activity_at.isoformat(),
        "message_count": thread.message_count,
        "unread": thread.is_unread_for(user),
        "closed_by_email": thread.closed_by.email if thread.closed_by_id else None,
        "closed_at": thread.closed_at.isoformat() if thread.closed_at else None,
        "close_reason": thread.close_reason,
        "close_reason_text": thread.close_reason_text,
        "satisfaction": thread.satisfaction,
        "items": [_serialize_item(i) for i in thread.items.all()],
        "can_close": (
            user.pk == thread.opened_by_id
            or can_force_close_thread(user, thread)
        ),
    }


def _serialize_message(message):
    return {
        "id": message.id,
        "author_id": message.author_id,
        "author_email": message.author.email,
        "side": message.side,
        "body": message.body,
        "created_at": message.created_at.isoformat(),
    }


def _thread_list_payload(queryset, user):
    threads = list(
        queryset.select_related("branch", "opened_by", "closed_by")
    )
    return {
        "threads": [_serialize_thread(t, user) for t in threads],
        "unread_count": sum(1 for t in threads if t.is_unread_for(user)),
    }


# ---------------------------------------------------------------------------
# Branch side (active branch required)
# ---------------------------------------------------------------------------


@active_branch_required
@require_GET
def branch_thread_list(request):
    queryset = ItemRequestThread.objects.for_branch(request.active_branch)
    return JsonResponse(_thread_list_payload(queryset, request.user))


@active_branch_required
@require_POST
def branch_thread_create(request):
    payload = _parse_json(request)
    try:
        thread = create_thread(
            request.active_branch,
            request.user,
            payload.get("subject"),
            payload.get("first_message"),
        )
    except ValidationError as exc:
        return _validation_error_response(exc)
    mark_read(thread, request.user)
    return JsonResponse(
        {"thread": _serialize_thread(thread, request.user)},
        status=201,
    )


@active_branch_required
@require_GET
def branch_thread_detail(request, thread_id):
    thread = _get_thread_or_404(thread_id, request.active_branch)
    mark_read(thread, request.user)
    return JsonResponse(
        {
            "thread": _serialize_thread(thread, request.user),
            "messages": [_serialize_message(m) for m in get_thread_messages(thread)],
            "history": [
                {
                    "user": log.user.email if log.user_id else None,
                    "action": log.action,
                    "reason": log.reason,
                    "created_at": log.created_at.isoformat(),
                }
                for log in get_thread_history(thread)
            ],
        }
    )


@active_branch_required
@require_POST
def branch_thread_post(request, thread_id):
    thread = _get_thread_or_404(thread_id, request.active_branch)
    payload = _parse_json(request)
    try:
        message = post_message(
            thread,
            request.user,
            payload.get("body"),
            ThreadMessage.Side.BRANCH,
        )
    except ValidationError as exc:
        return _validation_error_response(exc)
    return JsonResponse({"message": _serialize_message(message)}, status=201)


@active_branch_required
@require_POST
def branch_thread_close(request, thread_id):
    thread = _get_thread_or_404(thread_id, request.active_branch)
    payload = _parse_json(request)
    try:
        thread = close_thread(
            thread,
            request.user,
            payload.get("close_reason"),
            payload.get("close_reason_text", ""),
            payload.get("satisfaction"),
        )
    except ValidationError as exc:
        return _validation_error_response(exc)
    return JsonResponse({"thread": _serialize_thread(thread, request.user)})


# ---------------------------------------------------------------------------
# Warehouse side (capability gate)
# ---------------------------------------------------------------------------


@warehouse_threads_required
@require_GET
def warehouse_thread_list(request):
    """All threads, incl. inactive-branch threads (flagged, not zombies).

    Optional filters: ?branch_id=, ?status= (awaiting_warehouse /
    awaiting_branch / closed / open). Ordered oldest-awaiting first so
    nothing rots; closed threads last.
    """
    queryset = ItemRequestThread.objects.for_warehouse()
    branch_id = request.GET.get("branch_id")
    if branch_id:
        queryset = queryset.filter(branch_id=branch_id)
    status = request.GET.get("status")
    if status == "open":
        queryset = queryset.exclude(status=ItemRequestThread.Status.CLOSED)
    elif status:
        queryset = queryset.filter(status=status)
    if status == "closed":
        queryset = queryset.order_by("-last_activity_at")
    else:
        # oldest-awaiting first so nothing rots (closed threads excluded by filter)
        queryset = queryset.order_by("last_activity_at")
    return JsonResponse(_thread_list_payload(queryset, request.user))


@warehouse_threads_required
@require_GET
def warehouse_thread_detail(request, thread_id):
    thread = _get_thread_or_404(thread_id)
    mark_read(thread, request.user)
    return JsonResponse(
        {
            "thread": _serialize_thread(thread, request.user),
            "messages": [_serialize_message(m) for m in get_thread_messages(thread)],
            "history": [
                {
                    "user": log.user.email if log.user_id else None,
                    "action": log.action,
                    "reason": log.reason,
                    "created_at": log.created_at.isoformat(),
                }
                for log in get_thread_history(thread)
            ],
        }
    )


@warehouse_threads_required
@require_POST
def warehouse_thread_post(request, thread_id):
    thread = _get_thread_or_404(thread_id)
    payload = _parse_json(request)
    try:
        message = post_message(
            thread,
            request.user,
            payload.get("body"),
            ThreadMessage.Side.WAREHOUSE,
        )
    except ValidationError as exc:
        return _validation_error_response(exc)
    return JsonResponse({"message": _serialize_message(message)}, status=201)


@warehouse_threads_required
@require_POST
def warehouse_thread_link_items(request, thread_id):
    thread = _get_thread_or_404(thread_id)
    payload = _parse_json(request)
    item_ids = payload.get("item_ids", [])
    if not isinstance(item_ids, list):
        return _json_error("item_ids must be a list.", code="invalid_item_ids")
    try:
        thread = link_items(thread, request.user, item_ids)
    except ValidationError as exc:
        return _validation_error_response(exc)
    return JsonResponse({"thread": _serialize_thread(thread, request.user)})


@warehouse_threads_required
@require_POST
def warehouse_thread_close(request, thread_id):
    thread = _get_thread_or_404(thread_id)
    payload = _parse_json(request)
    try:
        thread = close_thread(
            thread,
            request.user,
            payload.get("close_reason"),
            payload.get("close_reason_text", ""),
            payload.get("satisfaction"),
        )
    except ValidationError as exc:
        return _validation_error_response(exc)
    return JsonResponse({"thread": _serialize_thread(thread, request.user)})


def search_items_for_link(request):
    """Minimal item search for the link-item control (warehouse only)."""
    if not is_warehouse_staff(request.user):
        return JsonResponse({"error": "Warehouse access required"}, status=403)
    query = (request.GET.get("q") or "").strip()
    items = Item.objects.filter(is_active=True)
    if query:
        items = items.filter(
            models.Q(internal_code__icontains=query)
            | models.Q(description__icontains=query)
        )
    items = items.select_related("family")[:20]
    return JsonResponse(
        {"items": [_serialize_item(i) for i in items]}
    )
