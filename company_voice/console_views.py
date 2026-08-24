import json

from django.core.exceptions import ValidationError
from django.http import Http404, JsonResponse
from django.views.decorators.http import require_GET, require_http_methods

from logging_utils import get_logger

from .models import VoiceComment, VoicePost
from .permissions import login_required_active
from .services import (
    EDIT_WINDOW,
    TAG_UNSET,
    add_comment,
    can_delete,
    can_edit,
    create_post,
    delete_comment,
    delete_post,
    display_name,
    edit_comment,
    edit_post,
    get_feed,
)

logger = get_logger("centcompras.company_voice")

DELETED_PLACEHOLDER = "[Deleted by author]"


def _json_error(message, status=400, code=None):
    payload = {"error": message}
    if code:
        payload["code"] = code
    return JsonResponse(payload, status=status)


def _validation_error_response(exc, status=None):
    code = getattr(exc, "code", None)
    if status is None:
        status = 409 if code == "stale_edit" else 400
    if isinstance(exc, ValidationError):
        message = exc.messages[0] if getattr(exc, "messages", None) else str(exc)
        return _json_error(message, status=status, code=code)
    return _json_error(str(exc), status=status, code=code)


def _parse_json(request):
    try:
        payload = json.loads(request.body or b"{}")
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise ValidationError("Request body must be valid JSON.", code="invalid_json")
    if not isinstance(payload, dict):
        raise ValidationError("Request body must be a JSON object.", code="invalid_json")
    return payload


def _get_post_or_404(post_id):
    try:
        return (
            VoicePost.objects.select_related("author", "sub_thread")
            .prefetch_related("sub_thread__comments__author")
            .get(pk=post_id)
        )
    except VoicePost.DoesNotExist:
        raise Http404("Post not found.")


def _get_comment_or_404(comment_id):
    try:
        return VoiceComment.objects.select_related(
            "author",
            "sub_thread",
            "sub_thread__post",
        ).get(pk=comment_id)
    except VoiceComment.DoesNotExist:
        raise Http404("Comment not found.")


def _serialize_comment(comment, user):
    deleted = comment.deleted or comment.sub_thread.deleted or comment.sub_thread.post.deleted
    is_mine = comment.author_id == user.pk
    return {
        "id": comment.id,
        "display_name": DELETED_PLACEHOLDER if deleted else display_name(comment.author, comment.is_anonymous),
        "is_mine": is_mine,
        "is_anonymous": comment.is_anonymous,
        "body": None if deleted else comment.body,
        "deleted": deleted,
        "created_at": comment.created_at.isoformat(),
        "updated_at": comment.updated_at.isoformat(),
        "edited": not deleted and comment.edited_at is not None,
        "can_edit": can_edit(user, comment) if not deleted else False,
        "can_delete": can_delete(user, comment) if not deleted else False,
    }


def _serialize_sub_thread(post, user):
    try:
        sub_thread = post.sub_thread
    except VoicePost.sub_thread.RelatedObjectDoesNotExist:
        return {
            "exists": False,
            "comment_count": 0,
            "comments": [],
        }
    comments = list(sub_thread.comments.all())
    deleted = post.deleted or sub_thread.deleted
    visible_comments = [_serialize_comment(c, user) for c in comments]
    live_count = sum(1 for c in visible_comments if not c["deleted"])
    return {
        "exists": True,
        "deleted": deleted,
        "comment_count": live_count,
        "comments": visible_comments,
    }


def _serialize_post(post, user):
    deleted = post.deleted
    is_mine = post.author_id == user.pk
    return {
        "id": post.id,
        "display_name": DELETED_PLACEHOLDER if deleted else display_name(post.author, post.is_anonymous),
        "is_mine": is_mine,
        "is_anonymous": post.is_anonymous,
        "tag": post.tag or None,
        "body": None if deleted else post.body,
        "deleted": deleted,
        "created_at": post.created_at.isoformat(),
        "updated_at": post.updated_at.isoformat(),
        "edited": not deleted and post.edited_at is not None,
        "can_edit": can_edit(user, post) if not deleted else False,
        "can_delete": can_delete(user, post) if not deleted else False,
        "sub_thread": _serialize_sub_thread(post, user),
    }


@login_required_active
@require_GET
def feed_api(request):
    posts = list(get_feed())
    return JsonResponse(
        {
            "posts": [_serialize_post(p, request.user) for p in posts],
            "edit_window_minutes": int(EDIT_WINDOW.total_seconds() // 60),
        }
    )


@login_required_active
@require_http_methods(["POST"])
def post_create(request):
    try:
        payload = _parse_json(request)
        post = create_post(
            request.user,
            payload.get("body"),
            tag=payload.get("tag"),
            is_anonymous=payload.get("is_anonymous", False),
        )
    except ValidationError as exc:
        return _validation_error_response(exc)
    post = _get_post_or_404(post.pk)
    return JsonResponse({"post": _serialize_post(post, request.user)}, status=201)


@login_required_active
@require_http_methods(["PATCH"])
def post_update(request, post_id):
    post = _get_post_or_404(post_id)
    try:
        payload = _parse_json(request)
        tag = payload.get("tag") if "tag" in payload else TAG_UNSET
        post = edit_post(
            request.user,
            post,
            payload.get("body"),
            tag=tag,
            expected_updated_at=payload.get("updated_at"),
        )
    except ValidationError as exc:
        return _validation_error_response(exc)
    post = _get_post_or_404(post.pk)
    return JsonResponse({"post": _serialize_post(post, request.user)})


@login_required_active
@require_http_methods(["DELETE"])
def post_delete(request, post_id):
    post = _get_post_or_404(post_id)
    try:
        delete_post(request.user, post)
    except ValidationError as exc:
        return _validation_error_response(exc)
    post = _get_post_or_404(post_id)
    return JsonResponse({"post": _serialize_post(post, request.user)})


@login_required_active
@require_http_methods(["POST"])
def comment_create(request, post_id):
    post = _get_post_or_404(post_id)
    try:
        payload = _parse_json(request)
        comment = add_comment(
            request.user,
            post,
            payload.get("body"),
            is_anonymous=payload.get("is_anonymous", False),
        )
    except ValidationError as exc:
        return _validation_error_response(exc)
    post = _get_post_or_404(post_id)
    return JsonResponse(
        {
            "comment": _serialize_comment(comment, request.user),
            "post": _serialize_post(post, request.user),
        },
        status=201,
    )


@login_required_active
@require_http_methods(["PATCH"])
def comment_update(request, comment_id):
    comment = _get_comment_or_404(comment_id)
    try:
        payload = _parse_json(request)
        comment = edit_comment(
            request.user,
            comment,
            payload.get("body"),
            expected_updated_at=payload.get("updated_at"),
        )
    except ValidationError as exc:
        return _validation_error_response(exc)
    return JsonResponse({"comment": _serialize_comment(comment, request.user)})


@login_required_active
@require_http_methods(["DELETE"])
def comment_delete(request, comment_id):
    comment = _get_comment_or_404(comment_id)
    try:
        delete_comment(request.user, comment)
    except ValidationError as exc:
        return _validation_error_response(exc)
    comment = _get_comment_or_404(comment_id)
    return JsonResponse({"comment": _serialize_comment(comment, request.user)})
