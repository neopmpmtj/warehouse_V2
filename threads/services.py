from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from logging_utils import get_logger

from branches.capabilities import branch_role
from branches.models import Branch
from products.models import Item

from .capabilities import can_force_close_thread, is_warehouse_staff
from .models import (
    ItemRequestThread,
    ItemRequestThreadChangeLog,
    ThreadMessage,
    ThreadReadState,
)

logger = get_logger("centcompras.threads")

SUBJECT_MAX_LENGTH = 255
REASON_MAX_LENGTH = 255


class ThreadClosedError(ValidationError):
    def __init__(self):
        super().__init__(
            "This thread is closed. No further messages can be posted.",
            code="thread_closed",
        )


class ClosePermissionDeniedError(ValidationError):
    def __init__(self):
        super().__init__(
            "Only the person who opened the thread can close it.",
            code="close_permission_denied",
        )


class CloseReasonRequiredError(ValidationError):
    def __init__(self):
        super().__init__(
            "A reason is required to close a thread.",
            code="close_reason_required",
        )


class CloseReasonTextRequiredError(ValidationError):
    def __init__(self):
        super().__init__(
            "A reason text is required when 'Other' is selected.",
            code="close_reason_text_required",
        )


class InvalidSatisfactionError(ValidationError):
    def __init__(self):
        super().__init__(
            "Satisfaction must be between 1 and 5 stars.",
            code="invalid_satisfaction",
        )


class InactiveBranchError(ValidationError):
    def __init__(self, branch=None):
        name = getattr(branch, "name", None) or "branch"
        super().__init__(
            f"Cannot use inactive branch '{name}'.",
            code="inactive_branch",
        )


class LinkPermissionDeniedError(ValidationError):
    def __init__(self):
        super().__init__(
            "Only warehouse staff can link items to a thread.",
            code="link_permission_denied",
        )


class NotBranchMemberError(ValidationError):
    def __init__(self):
        super().__init__(
            "The opener must be a member of the branch.",
            code="not_branch_member",
        )


class ItemNotFoundError(ValidationError):
    def __init__(self):
        super().__init__(
            "One or more items were not found.",
            code="item_not_found",
        )


def _resolve_thread(thread):
    if isinstance(thread, ItemRequestThread):
        return thread
    return ItemRequestThread.objects.get(pk=thread)


def _lock_thread(thread):
    return ItemRequestThread.objects.select_for_update().get(pk=_resolve_thread(thread).pk)


def _ensure_branch_active(branch):
    if not Branch.objects.filter(pk=branch.pk, is_active=True).exists():
        raise InactiveBranchError(branch)


def _require_text(value, field_name, code, message, max_length):
    if value is None:
        text = ""
    elif isinstance(value, str):
        text = value.strip()
    else:
        raise ValidationError(f"{field_name} must be a string.", code=code)
    if not text:
        raise ValidationError(message, code=code)
    if len(text) > max_length:
        raise ValidationError(
            f"{field_name} must be {max_length} characters or fewer.",
            code=code,
        )
    return text


def _require_subject(subject):
    return _require_text(
        subject,
        "Subject",
        "subject_required",
        "A subject is required.",
        SUBJECT_MAX_LENGTH,
    )


def _require_body(body):
    return _require_text(
        body,
        "Message",
        "message_required",
        "A message is required.",
        10000,
    )


def _require_close_reason(reason, reason_text):
    if reason is None:
        reason = ""
    elif not isinstance(reason, str):
        raise CloseReasonRequiredError()
    else:
        reason = reason.strip()
    if reason not in ItemRequestThread.CloseReason.values:
        raise CloseReasonRequiredError()
    if reason == ItemRequestThread.CloseReason.OTHER:
        if reason_text is None:
            text = ""
        elif not isinstance(reason_text, str):
            raise CloseReasonTextRequiredError()
        else:
            text = reason_text.strip()
        if not text:
            raise CloseReasonTextRequiredError()
        if len(text) > REASON_MAX_LENGTH:
            raise ValidationError(
                f"Reason text must be {REASON_MAX_LENGTH} characters or fewer.",
                code="close_reason_text_too_long",
            )
        reason_text = text
    else:
        reason_text = ""
    return reason, reason_text


def _require_satisfaction(satisfaction):
    """Validate 1–5 stars; default 1 so an unattended request can signal low satisfaction.

    Rejects bools and non-ints (``True`` / ``3.7`` must not coerce).
    """
    if satisfaction is None:
        return ItemRequestThread.Satisfaction.ONE
    if isinstance(satisfaction, bool) or not isinstance(satisfaction, int):
        raise InvalidSatisfactionError()
    if satisfaction not in ItemRequestThread.Satisfaction.values:
        raise InvalidSatisfactionError()
    return satisfaction


def _item_pk(item):
    pk = getattr(item, "pk", item)
    if isinstance(pk, bool) or pk is None:
        raise ItemNotFoundError()
    if isinstance(pk, int):
        return pk
    if isinstance(pk, str) and pk.strip().isdigit():
        return int(pk.strip())
    raise ItemNotFoundError()


def _log(thread, user, action, changes, reason=""):
    ItemRequestThreadChangeLog.objects.create(
        thread=thread,
        user=user,
        action=action,
        changes=changes,
        reason=(reason or "").strip(),
    )


def _bump(thread, user=None):
    thread.last_activity_at = timezone.now()
    thread.save(update_fields=["last_activity_at", "updated_at"])


def _flip_status(thread, side):
    """Return the new status after a post by ``side``.

    State = whose turn it is to respond. A post by the side that is expected
    to respond flips the turn to the other side; a post by the other side
    (or a second post in a row by the same side) keeps the state — e.g. two
    warehouse replies in a row stay ``awaiting_branch``.
    """
    if side == ThreadMessage.Side.BRANCH and thread.status == ItemRequestThread.Status.AWAITING_BRANCH:
        return ItemRequestThread.Status.AWAITING_WAREHOUSE
    if side == ThreadMessage.Side.WAREHOUSE and thread.status == ItemRequestThread.Status.AWAITING_WAREHOUSE:
        return ItemRequestThread.Status.AWAITING_BRANCH
    return thread.status


@transaction.atomic
def create_thread(branch, opened_by, subject, first_message):
    """Open a thread (status ``awaiting_warehouse``) with its first message.

    The branch must be active (mirror ``_ensure_branch_active`` in orders).
    The opener must be a member of that branch.
    """
    _ensure_branch_active(branch)
    if branch_role(opened_by, branch) is None:
        raise NotBranchMemberError()
    subject = _require_subject(subject)
    first_message = _require_body(first_message)

    now = timezone.now()
    thread = ItemRequestThread(
        branch=branch,
        opened_by=opened_by,
        subject=subject,
        status=ItemRequestThread.Status.AWAITING_WAREHOUSE,
        last_activity_at=now,
        message_count=1,
    )
    thread.full_clean(exclude=None, validate_unique=False, validate_constraints=False)
    thread.save()

    ThreadMessage.objects.create(
        thread=thread,
        author=opened_by,
        side=ThreadMessage.Side.BRANCH,
        body=first_message,
    )
    # The opener wrote it — they have read it. Other participants start unread.
    ThreadReadState.objects.update_or_create(
        thread=thread,
        user=opened_by,
        defaults={"last_read_at": now},
    )
    _log(
        thread,
        opened_by,
        ItemRequestThreadChangeLog.Action.CREATED,
        {
            "branch": {"id": branch.id, "name": branch.name},
            "subject": thread.subject,
            "status": thread.status,
        },
    )
    logger.info(
        "Created request thread id=%s branch=%s subject=%r user=%s",
        thread.id,
        branch.name,
        thread.subject,
        getattr(opened_by, "email", None),
    )
    return thread


@transaction.atomic
def post_message(thread, user, body, side):
    """Append a message and flip the awaiting state (lock on post — no race).

    ``side`` is explicit (branch|warehouse), never inferred from identity:
    dual warehouse+branch users exist (e.g. ``branch.dual@``).
    """
    thread = _lock_thread(thread)
    if thread.status == ItemRequestThread.Status.CLOSED:
        raise ThreadClosedError()
    if side not in ThreadMessage.Side.values:
        raise ValidationError("Invalid message side.", code="invalid_side")
    body = _require_body(body)

    message = ThreadMessage.objects.create(
        thread=thread,
        author=user,
        side=side,
        body=body,
    )
    new_status = _flip_status(thread, side)
    thread.status = new_status
    thread.message_count += 1
    thread.last_activity_at = message.created_at
    thread.save(update_fields=["status", "message_count", "last_activity_at", "updated_at"])
    logger.info(
        "Posted %s message to thread id=%s user=%s",
        side,
        thread.id,
        getattr(user, "email", None),
    )
    return message


@transaction.atomic
def close_thread(thread, user, reason, reason_text="", satisfaction=None):
    """Close a thread. Opener only, or an override (closer's role, never the opener's).

    Override: branch manager/admin of that branch, or warehouse admin. The
    check uses the *closer's* role so a deactivated opener never blocks a
    legitimate close. Reason required; ``other`` requires text. Satisfaction
    (1–5 stars) is recorded only when the **opener** closes (default 1 so an
    unattended request can signal low satisfaction). Override closes store
    ``satisfaction=None`` so the closer cannot rate on the opener's behalf.
    """
    thread = _lock_thread(thread)
    if thread.status == ItemRequestThread.Status.CLOSED:
        return thread

    is_opener = getattr(user, "pk", None) == thread.opened_by_id
    if not is_opener and not can_force_close_thread(user, thread):
        raise ClosePermissionDeniedError()

    reason, reason_text = _require_close_reason(reason, reason_text)
    if is_opener:
        satisfaction = _require_satisfaction(satisfaction)
    else:
        satisfaction = None

    thread.status = ItemRequestThread.Status.CLOSED
    thread.closed_by = user
    thread.closed_at = timezone.now()
    thread.close_reason = reason
    thread.close_reason_text = reason_text
    thread.satisfaction = satisfaction
    thread.last_activity_at = thread.closed_at
    thread.save(
        update_fields=[
            "status",
            "closed_by",
            "closed_at",
            "close_reason",
            "close_reason_text",
            "satisfaction",
            "last_activity_at",
            "updated_at",
        ]
    )
    _log(
        thread,
        user,
        ItemRequestThreadChangeLog.Action.CLOSED,
        {
            "reason": reason,
            "reason_text": reason_text,
            "satisfaction": satisfaction,
            "override": not is_opener,
            "closed_by": getattr(user, "email", None),
        },
        reason=reason_text or reason,
    )
    logger.info(
        "Closed request thread id=%s user=%s override=%s reason=%s satisfaction=%s",
        thread.id,
        getattr(user, "email", None),
        not is_opener,
        reason,
        satisfaction,
    )
    return thread


@transaction.atomic
def link_items(thread, user, items):
    """Attach created Item(s) to a thread for traceability (warehouse staff only).

    Allowed after close — the opener often closes the thread as the item
    lands. Only **newly** linked items write a changelog row. Unknown ids
    raise ``ItemNotFoundError`` (no silent no-op).
    """
    if not is_warehouse_staff(user):
        raise LinkPermissionDeniedError()

    thread = _lock_thread(thread)
    item_ids = []
    seen = set()
    for item in items:
        pk = _item_pk(item)
        if pk in seen:
            continue
        seen.add(pk)
        item_ids.append(pk)
    if not item_ids:
        raise ValidationError("No items to link.", code="no_items")
    linked = list(Item.objects.filter(pk__in=item_ids))
    if len(linked) != len(item_ids):
        raise ItemNotFoundError()
    already = set(thread.items.values_list("pk", flat=True))
    new_items = [item for item in linked if item.pk not in already]
    if not new_items:
        return thread
    thread.items.add(*new_items)
    _log(
        thread,
        user,
        ItemRequestThreadChangeLog.Action.ITEM_LINKED,
        {
            "items": [
                {
                    "id": item.id,
                    "internal_code": item.internal_code,
                    "description": item.description,
                }
                for item in new_items
            ]
        },
    )
    logger.info(
        "Linked %d item(s) to thread id=%s user=%s",
        len(new_items),
        thread.id,
        getattr(user, "email", None),
    )
    return thread


@transaction.atomic
def mark_read(thread, user):
    """Upsert the user's read cursor on a thread."""
    ThreadReadState.objects.update_or_create(
        thread=thread,
        user=user,
        defaults={"last_read_at": timezone.now()},
    )


def get_thread_messages(thread):
    return thread.messages.select_related("author").order_by("created_at")


def get_thread_history(thread):
    return thread.change_logs.select_related("user").order_by("-created_at")
