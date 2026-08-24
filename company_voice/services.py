from datetime import datetime, timedelta

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from logging_utils import get_logger

from .models import VoiceChangeLog, VoiceComment, VoicePost, VoiceSubThread

logger = get_logger("centcompras.company_voice")

BODY_MAX_LENGTH = 4000
EDIT_WINDOW = timedelta(minutes=15)
TAG_UNSET = object()

VALID_TAGS = {choice[0] for choice in VoicePost.Tag.choices}


class EmptyBodyError(ValidationError):
    def __init__(self):
        super().__init__("Message body cannot be empty.", code="empty_body")


class BodyTooLongError(ValidationError):
    def __init__(self):
        super().__init__(
            f"Message body cannot exceed {BODY_MAX_LENGTH} characters.",
            code="body_too_long",
        )


class InvalidTagError(ValidationError):
    def __init__(self):
        super().__init__("Invalid tag.", code="invalid_tag")


class NotAuthorError(ValidationError):
    def __init__(self):
        super().__init__(
            "Only the author can change or delete this message.",
            code="not_author",
        )


class EditWindowExpiredError(ValidationError):
    def __init__(self):
        super().__init__(
            "The edit window has expired.",
            code="edit_window_expired",
        )


class AlreadyDeletedError(ValidationError):
    def __init__(self):
        super().__init__(
            "This message has been deleted.",
            code="already_deleted",
        )


class PostDeletedError(ValidationError):
    def __init__(self):
        super().__init__(
            "This post has been deleted.",
            code="post_deleted",
        )


class StaleEditError(ValidationError):
    def __init__(self):
        super().__init__(
            "This message was changed in another tab. Refresh and try again.",
            code="stale_edit",
        )


class InvalidAnonymousError(ValidationError):
    def __init__(self):
        super().__init__(
            "is_anonymous must be a boolean.",
            code="invalid_anonymous",
        )


def _normalize_body(body):
    if body is None:
        return ""
    if not isinstance(body, str):
        raise ValidationError("Body must be a string.", code="invalid_body")
    return body.strip()


def _validate_body(body):
    normalized = _normalize_body(body)
    if not normalized:
        raise EmptyBodyError()
    if len(normalized) > BODY_MAX_LENGTH:
        raise BodyTooLongError()
    return normalized


def _validate_tag(tag):
    if tag in (None, ""):
        return ""
    if not isinstance(tag, str):
        raise InvalidTagError()
    tag = tag.strip().lower()
    if tag not in VALID_TAGS:
        raise InvalidTagError()
    return tag


def _validate_anonymous(is_anonymous):
    if not isinstance(is_anonymous, bool):
        raise InvalidAnonymousError()
    return is_anonymous


def _within_edit_window(created_at, now=None):
    now = now or timezone.now()
    return now - created_at <= EDIT_WINDOW


def _parse_expected_updated_at(value):
    if value is None:
        raise ValidationError("updated_at is required.", code="updated_at_required")
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        parsed = parse_datetime(value)
        if parsed is None:
            raise ValidationError(
                "updated_at must be an ISO timestamp.",
                code="invalid_updated_at",
            )
    else:
        raise ValidationError(
            "updated_at must be an ISO timestamp.",
            code="invalid_updated_at",
        )
    if timezone.is_naive(parsed):
        parsed = timezone.make_aware(parsed, timezone.utc)
    return parsed


def _require_fresh(obj, expected_updated_at):
    expected = _parse_expected_updated_at(expected_updated_at)
    if expected != obj.updated_at:
        raise StaleEditError()


def _log_change(post, user, action, comment=None, changes=None):
    VoiceChangeLog.objects.create(
        post=post,
        comment=comment,
        user=user,
        action=action,
        changes=changes or {},
    )


def display_name(user, is_anonymous, *, viewer=None):
    """Public display label for a message author."""
    if is_anonymous:
        return "Anonymous"
    first = (getattr(user, "first_name", "") or "").strip()
    if first:
        return first
    email = getattr(user, "email", "") or ""
    if "@" in email:
        return email.split("@", 1)[0]
    return email or "User"


def create_post(user, body, tag=None, is_anonymous=False):
    body = _validate_body(body)
    tag = _validate_tag(tag)
    is_anonymous = _validate_anonymous(is_anonymous)
    post = VoicePost.objects.create(
        author=user,
        body=body,
        tag=tag,
        is_anonymous=is_anonymous,
    )
    _log_change(
        post,
        user,
        VoiceChangeLog.Action.POST_CREATED,
        changes={"tag": tag, "is_anonymous": is_anonymous},
    )
    logger.info("Voice post %s created by user %s", post.pk, user.pk)
    return post


@transaction.atomic
def edit_post(user, post, body, tag=TAG_UNSET, *, expected_updated_at):
    post = VoicePost.objects.select_for_update().get(pk=post.pk)
    if post.deleted:
        raise AlreadyDeletedError()
    if post.author_id != user.pk:
        raise NotAuthorError()
    if not _within_edit_window(post.created_at):
        raise EditWindowExpiredError()
    _require_fresh(post, expected_updated_at)
    body = _validate_body(body)
    changes = {"body": body}
    if tag is not TAG_UNSET:
        post.tag = _validate_tag(tag)
        changes["tag"] = post.tag
    post.body = body
    post.edited_at = timezone.now()
    post.save(update_fields=["body", "tag", "edited_at", "updated_at"])
    _log_change(post, user, VoiceChangeLog.Action.POST_EDITED, changes=changes)
    logger.info("Voice post %s edited by user %s", post.pk, user.pk)
    return post


@transaction.atomic
def delete_post(user, post):
    post = VoicePost.objects.select_for_update().get(pk=post.pk)
    if post.deleted:
        raise AlreadyDeletedError()
    if post.author_id != user.pk:
        raise NotAuthorError()
    now = timezone.now()
    post.deleted_at = now
    post.save(update_fields=["deleted_at", "updated_at"])
    sub_thread = VoiceSubThread.objects.filter(post=post).first()
    if sub_thread is not None and not sub_thread.deleted:
        sub_thread.deleted_at = now
        sub_thread.save(update_fields=["deleted_at"])
        VoiceComment.objects.filter(
            sub_thread=sub_thread,
            deleted_at__isnull=True,
        ).update(deleted_at=now, updated_at=now)
    _log_change(
        post,
        user,
        VoiceChangeLog.Action.POST_DELETED,
        changes={"cascaded_sub_thread": sub_thread is not None},
    )
    logger.info("Voice post %s soft-deleted by user %s", post.pk, user.pk)
    return post


def _get_or_create_sub_thread(post):
    if post.deleted:
        raise PostDeletedError()
    try:
        with transaction.atomic():
            sub_thread, _created = VoiceSubThread.objects.get_or_create(post=post)
    except IntegrityError:
        sub_thread = VoiceSubThread.objects.get(post=post)
    if sub_thread.deleted:
        raise PostDeletedError()
    return sub_thread


@transaction.atomic
def add_comment(user, post, body, is_anonymous=False):
    body = _validate_body(body)
    is_anonymous = _validate_anonymous(is_anonymous)
    locked = VoicePost.objects.select_for_update().get(pk=post.pk)
    sub_thread = _get_or_create_sub_thread(locked)
    comment = VoiceComment.objects.create(
        sub_thread=sub_thread,
        author=user,
        body=body,
        is_anonymous=is_anonymous,
    )
    _log_change(
        locked,
        user,
        VoiceChangeLog.Action.COMMENT_CREATED,
        comment=comment,
        changes={"is_anonymous": is_anonymous},
    )
    logger.info(
        "Voice comment %s added to post %s by user %s",
        comment.pk,
        locked.pk,
        user.pk,
    )
    return comment


@transaction.atomic
def edit_comment(user, comment, body, *, expected_updated_at):
    comment = (
        VoiceComment.objects.select_for_update()
        .select_related("sub_thread", "sub_thread__post")
        .get(pk=comment.pk)
    )
    if comment.deleted:
        raise AlreadyDeletedError()
    if comment.author_id != user.pk:
        raise NotAuthorError()
    if not _within_edit_window(comment.created_at):
        raise EditWindowExpiredError()
    if comment.sub_thread.deleted or comment.sub_thread.post.deleted:
        raise PostDeletedError()
    _require_fresh(comment, expected_updated_at)
    body = _validate_body(body)
    comment.body = body
    comment.edited_at = timezone.now()
    comment.save(update_fields=["body", "edited_at", "updated_at"])
    _log_change(
        comment.sub_thread.post,
        user,
        VoiceChangeLog.Action.COMMENT_EDITED,
        comment=comment,
        changes={"body": body},
    )
    logger.info("Voice comment %s edited by user %s", comment.pk, user.pk)
    return comment


@transaction.atomic
def delete_comment(user, comment):
    comment = (
        VoiceComment.objects.select_for_update()
        .select_related("sub_thread", "sub_thread__post")
        .get(pk=comment.pk)
    )
    if comment.deleted:
        raise AlreadyDeletedError()
    if comment.author_id != user.pk:
        raise NotAuthorError()
    if comment.sub_thread.deleted or comment.sub_thread.post.deleted:
        raise PostDeletedError()
    comment.deleted_at = timezone.now()
    comment.save(update_fields=["deleted_at", "updated_at"])
    _log_change(
        comment.sub_thread.post,
        user,
        VoiceChangeLog.Action.COMMENT_DELETED,
        comment=comment,
    )
    logger.info("Voice comment %s soft-deleted by user %s", comment.pk, user.pk)
    return comment


def get_feed():
    return (
        VoicePost.objects.select_related("author", "sub_thread")
        .prefetch_related("sub_thread__comments__author")
        .order_by("created_at")
    )


def can_edit(user, obj):
    if obj.deleted or obj.author_id != user.pk:
        return False
    return _within_edit_window(obj.created_at)


def can_delete(user, obj):
    if obj.deleted:
        return False
    return obj.author_id == user.pk
