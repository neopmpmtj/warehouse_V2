from django.conf import settings
from django.db import models
from django.db.models.functions import Lower


class Branch(models.Model):
    """A satellite branch. Tenancy only — no request or stock logic lives here."""

    name = models.CharField(max_length=255)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                Lower("name"),
                name="unique_branch_name_ci",
            ),
        ]

    def __str__(self):
        return self.name


class BranchMembership(models.Model):
    """A user's role on a branch. One role per user per branch."""

    class Role(models.TextChoices):
        OPERATOR = "operator", "Operator"
        MANAGER = "manager", "Manager"
        ADMIN = "admin", "Admin"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="branch_memberships",
    )
    branch = models.ForeignKey(
        Branch,
        on_delete=models.PROTECT,
        related_name="memberships",
    )
    role = models.CharField(
        max_length=16,
        choices=Role.choices,
        default=Role.OPERATOR,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["branch__name", "user__email"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "branch"],
                name="unique_branch_membership_user_branch",
            ),
        ]

    def __str__(self):
        return f"{self.user.email} @ {self.branch.name} ({self.role})"


class BranchCommercialSettings(models.Model):
    """Company-wide branch commercial mode (singleton, pk=1)."""

    class Mode(models.TextChoices):
        UNPRICED = "unpriced", "Unpriced — quantity only"
        PRICED = "priced", "Priced — selling prices and EUR caps"

    mode = models.CharField(
        max_length=16,
        choices=Mode.choices,
        default=Mode.UNPRICED,
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "branch commercial settings"
        verbose_name_plural = "branch commercial settings"

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Branch commercial mode: {self.get_mode_display()}"
