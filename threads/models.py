from django.conf import settings
from django.db import models


class ItemRequestThreadQuerySet(models.QuerySet):
    def for_branch(self, branch):
        return self.filter(branch=branch)

    def for_user_branches(self, user):
        return self.filter(branch__memberships__user=user)

    def for_warehouse(self):
        """Warehouse sees all threads, including inactive-branch threads (flagged)."""
        return self.all()


class ItemRequestThread(models.Model):
    """A written request thread between a branch and the warehouse.

    Used when the needed item does NOT exist in the catalogue yet: the branch
    describes it in free text, warehouse staff engage until understood, and
    the warehouse creates the item via the normal item console. Only the
    opener closes the thread (managers/admins may force-close as override).
    """

    class Status(models.TextChoices):
        AWAITING_WAREHOUSE = "awaiting_warehouse", "Awaiting warehouse"
        AWAITING_BRANCH = "awaiting_branch", "Awaiting branch"
        CLOSED = "closed", "Closed"

    class CloseReason(models.TextChoices):
        REQUEST_SATISFIED = "request_satisfied", "Request Satisfied"
        OTHER = "other", "Other"

    branch = models.ForeignKey(
        "branches.Branch",
        on_delete=models.PROTECT,
        related_name="request_threads",
    )
    opened_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="request_threads_opened",
    )
    subject = models.CharField(max_length=255)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.AWAITING_WAREHOUSE,
    )
    last_activity_at = models.DateTimeField(
        help_text="Denormalized: bumped on every create/post/close (D5 philosophy)."
    )
    message_count = models.PositiveIntegerField(default=0)
    closed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="request_threads_closed",
    )
    closed_at = models.DateTimeField(null=True, blank=True)
    close_reason = models.CharField(
        max_length=30,
        choices=CloseReason.choices,
        blank=True,
    )
    close_reason_text = models.CharField(max_length=255, blank=True)
    items = models.ManyToManyField(
        "products.Item",
        blank=True,
        related_name="request_threads",
        help_text="Traceability: items created from this thread, linked by the warehouse.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = ItemRequestThreadQuerySet.as_manager()

    class Meta:
        ordering = ["-last_activity_at"]
        indexes = [
            models.Index(fields=["branch", "status"], name="thread_branch_status_idx"),
            models.Index(fields=["-last_activity_at"], name="thread_last_activity_idx"),
        ]

    def __str__(self):
        return f"THREAD #{self.pk} — {self.subject} ({self.branch.name}, {self.status})"

    def open(self):
        return self.status != self.Status.CLOSED

    def closed(self):
        return self.status == self.Status.CLOSED

    def is_unread_for(self, user, read_attr="my_read"):
        """True when activity happened after the user's last read (or never read)."""
        states = getattr(self, read_attr, None)
        if states:
            last_read = states[0].last_read_at
        else:
            last_read = (
                ThreadReadState.objects.filter(thread=self, user=user)
                .values_list("last_read_at", flat=True)
                .first()
            )
        return last_read is None or self.last_activity_at > last_read


class ThreadMessage(models.Model):
    """One message in a thread. Append-only (no edit/delete) — audit-by-design."""

    class Side(models.TextChoices):
        BRANCH = "branch", "Branch"
        WAREHOUSE = "warehouse", "Warehouse"

    thread = models.ForeignKey(
        ItemRequestThread,
        on_delete=models.CASCADE,
        related_name="messages",
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="thread_messages",
    )
    side = models.CharField(
        max_length=16,
        choices=Side.choices,
        help_text="Explicit poster side — never inferred from identity (dual users exist).",
    )
    body = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"#{self.thread_id} [{self.side}] {self.author.email} @ {self.created_at:%Y-%m-%d %H:%M}"


class ThreadReadState(models.Model):
    """In-app read cursor (no email in this phase). One cursor per participant."""

    thread = models.ForeignKey(
        ItemRequestThread,
        on_delete=models.CASCADE,
        related_name="read_states",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="thread_read_states",
    )
    last_read_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["thread", "user"],
                name="unique_thread_read_state",
            ),
        ]

    def __str__(self):
        return f"{self.user.email} read #{self.thread_id} @ {self.last_read_at:%Y-%m-%d %H:%M}"


class ItemRequestThreadChangeLog(models.Model):
    """Lifecycle audit for a thread: created / item_linked / closed.

    Messages are their own audit (append-only) — they are NOT logged here.
    """

    class Action(models.TextChoices):
        CREATED = "created", "Created"
        ITEM_LINKED = "item_linked", "Item linked"
        CLOSED = "closed", "Closed"

    thread = models.ForeignKey(
        ItemRequestThread,
        on_delete=models.PROTECT,
        related_name="change_logs",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="request_thread_change_logs",
    )
    action = models.CharField(max_length=30, choices=Action.choices)
    changes = models.JSONField(default=dict)
    reason = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"#{self.thread_id} {self.action} @ {self.created_at:%Y-%m-%d %H:%M}"
