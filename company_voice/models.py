from django.conf import settings
from django.db import models


class VoicePost(models.Model):
    """Top-level entry in the company-wide Company Voice feed."""

    class Tag(models.TextChoices):
        PRAISE = "praise", "Praise"
        CONCERN = "concern", "Concern"
        SUGGESTION = "suggestion", "Suggestion"
        WISH = "wish", "Wish"

    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="voice_posts",
    )
    body = models.TextField()
    tag = models.CharField(
        max_length=20,
        choices=Tag.choices,
        blank=True,
    )
    is_anonymous = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    edited_at = models.DateTimeField(null=True, blank=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["created_at"]
        indexes = [
            models.Index(fields=["created_at"], name="voice_post_created_idx"),
            models.Index(fields=["deleted_at"], name="voice_post_deleted_idx"),
        ]

    def __str__(self):
        return f"VoicePost #{self.pk} by {self.author_id}"

    @property
    def deleted(self):
        return self.deleted_at is not None


class VoiceSubThread(models.Model):
    """At most one sub-thread per top-level post."""

    post = models.OneToOneField(
        VoicePost,
        on_delete=models.CASCADE,
        related_name="sub_thread",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["deleted_at"], name="voice_subthread_deleted_idx"),
        ]

    def __str__(self):
        return f"VoiceSubThread for post #{self.post_id}"

    @property
    def deleted(self):
        return self.deleted_at is not None


class VoiceComment(models.Model):
    """A message inside a post's sub-thread."""

    sub_thread = models.ForeignKey(
        VoiceSubThread,
        on_delete=models.CASCADE,
        related_name="comments",
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="voice_comments",
    )
    body = models.TextField()
    is_anonymous = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    edited_at = models.DateTimeField(null=True, blank=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["created_at"]
        indexes = [
            models.Index(fields=["created_at"], name="voice_comment_created_idx"),
            models.Index(fields=["deleted_at"], name="voice_comment_deleted_idx"),
        ]

    def __str__(self):
        return f"VoiceComment #{self.pk} on sub-thread #{self.sub_thread_id}"

    @property
    def deleted(self):
        return self.deleted_at is not None


class VoiceChangeLog(models.Model):
    """Audit row for Company Voice create / edit / delete."""

    class Action(models.TextChoices):
        POST_CREATED = "post_created", "Post created"
        POST_EDITED = "post_edited", "Post edited"
        POST_DELETED = "post_deleted", "Post deleted"
        COMMENT_CREATED = "comment_created", "Comment created"
        COMMENT_EDITED = "comment_edited", "Comment edited"
        COMMENT_DELETED = "comment_deleted", "Comment deleted"

    post = models.ForeignKey(
        VoicePost,
        on_delete=models.PROTECT,
        related_name="change_logs",
    )
    comment = models.ForeignKey(
        VoiceComment,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="change_logs",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="voice_change_logs",
    )
    action = models.CharField(max_length=30, choices=Action.choices)
    changes = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"VoiceChangeLog {self.action} post #{self.post_id}"
