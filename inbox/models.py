from django.conf import settings
from django.db import models


class SectionCursor(models.Model):
    """Per-user last visit to a work-queue section (dashboard 'new' badges)."""

    class Section(models.TextChoices):
        WAREHOUSE_REQUESTS = "warehouse_requests", "Warehouse requests"
        WAREHOUSE_INBOUND = "warehouse_inbound", "Incoming from branches"
        WAREHOUSE_RETURNS = "warehouse_returns", "Returned dispatches"
        BRANCH_RECEIPTS = "branch_receipts", "Branch receipts"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="inbox_section_cursors",
    )
    section = models.CharField(max_length=32, choices=Section.choices, db_index=True)
    branch = models.ForeignKey(
        "branches.Branch",
        on_delete=models.CASCADE,
        related_name="inbox_section_cursors",
        null=True,
        blank=True,
    )
    last_seen_at = models.DateTimeField()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "section"],
                condition=models.Q(branch__isnull=True),
                name="unique_inbox_cursor_warehouse",
            ),
            models.UniqueConstraint(
                fields=["user", "section", "branch"],
                condition=models.Q(branch__isnull=False),
                name="unique_inbox_cursor_branch",
            ),
        ]
        indexes = [
            models.Index(fields=["user", "section", "branch"], name="inbox_cursor_lookup_idx"),
        ]

    def __str__(self):
        loc = self.branch_id or "warehouse"
        return f"{self.user_id} {self.section} {loc} @ {self.last_seen_at:%Y-%m-%d %H:%M}"
