from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from logging_utils import get_logger

from accounts.groups import warehouse_group_name

from .models import Branch, BranchMembership

logger = get_logger("centcompras.branches")

SESSION_KEY = "active_branch_id"

BRANCH_HOME_URL = "/branch/catalog/"
BRANCH_SELECT_URL = "/branch/select/"


class DuplicateBranchNameError(ValidationError):
    pass


class InvalidBranchRoleError(ValidationError):
    pass


def _normalize_branch_name(name):
    return (name or "").strip()


def validate_branch_name_available(name, exclude_branch_id=None):
    name = _normalize_branch_name(name)
    if not name:
        raise ValidationError("Branch name is required.")

    queryset = Branch.objects.filter(name__iexact=name)
    if exclude_branch_id is not None:
        queryset = queryset.exclude(pk=exclude_branch_id)
    if queryset.exists():
        raise DuplicateBranchNameError(name)
    return name


def create_branch(name, is_active=True):
    """Create a branch. Name is case-insensitive unique (family pattern)."""
    name = validate_branch_name_available(name)
    branch = Branch(name=name, is_active=is_active)
    try:
        with transaction.atomic():
            branch.full_clean(validate_unique=False, validate_constraints=False)
            branch.save()
    except IntegrityError:
        validate_branch_name_available(name, exclude_branch_id=branch.pk)
        raise

    logger.info("Created branch id=%s name=%r", branch.id, branch.name)
    return branch


def assign_membership(user, branch, role):
    """Upsert a user's role on a branch (one role per user per branch)."""
    if role not in BranchMembership.Role.values:
        raise InvalidBranchRoleError(role)

    membership, created = BranchMembership.objects.get_or_create(
        user=user,
        branch=branch,
        defaults={"role": role},
    )
    if not created and membership.role != role:
        membership.role = role
        membership.save(update_fields=["role", "updated_at"])

    logger.info(
        "Branch membership user=%s branch=%s role=%s created=%s",
        getattr(user, "email", None),
        getattr(branch, "name", None),
        role,
        created,
    )
    return membership


def get_memberships(user):
    if not getattr(user, "pk", None):
        return BranchMembership.objects.none()
    return BranchMembership.objects.filter(user=user).select_related("branch")


def get_active_memberships(user):
    return get_memberships(user).filter(branch__is_active=True)


def get_active_branch(request):
    """Return the branch stored in the session, if the membership still holds.

    Clears the session key when the membership was revoked or the branch is
    inactive (lock 9: in-flight work can still finish in later slices).
    """
    user = getattr(request, "user", None)
    branch_id = request.session.get(SESSION_KEY)
    if not branch_id or not getattr(user, "pk", None):
        return None

    membership = (
        BranchMembership.objects.filter(
            user=user,
            branch_id=branch_id,
            branch__is_active=True,
        )
        .select_related("branch")
        .first()
    )
    if membership is None:
        request.session.pop(SESSION_KEY, None)
        return None
    return membership.branch


def set_active_branch(request, branch):
    if branch is None:
        clear_active_branch(request)
        return None

    valid = BranchMembership.objects.filter(
        user=request.user,
        branch=branch,
        branch__is_active=True,
    ).exists()
    if not valid:
        raise ValidationError("No active membership for this branch.")

    request.session[SESSION_KEY] = branch.pk
    return branch


def clear_active_branch(request):
    request.session.pop(SESSION_KEY, None)


def post_login_redirect(user):
    """Return the post-login landing URL per lock 5.

    - Warehouse group (including dual warehouse+branch) -> "/"
    - Branch-only with exactly one active membership -> branch home
    - Branch-only with zero or several active memberships -> picker
    """
    if not getattr(user, "is_authenticated", False) or not getattr(user, "is_active", False):
        return None
    if getattr(user, "is_superuser", False) or warehouse_group_name(user) is not None:
        return "/"

    active = list(get_active_memberships(user))
    if len(active) == 1:
        return BRANCH_HOME_URL
    return BRANCH_SELECT_URL


def post_login_landing(request):
    """Return the post-login landing URL, selecting the branch first.

    ``post_login_redirect`` returns the branch home for a branch-only user with
    exactly one active membership, but that page reads ``request.active_branch``
    from the session. Auto-select the sole branch here so the landing page
    renders directly instead of bouncing through the picker.
    """
    user = getattr(request, "user", None)
    landing = post_login_redirect(user)
    if landing == BRANCH_HOME_URL:
        active = list(get_active_memberships(user))
        if len(active) == 1:
            set_active_branch(request, active[0].branch)
    return landing


def availability_hint(item):
    """Lock 7 stock hint for branch UI: ``none`` / ``low`` / ``in stock``.

    Derived from *available* warehouse quantity (on-hand minus reservations)
    plus reorder level. The exact quantity is never exposed to the branch.
    None means nothing is free to ship today; it does not block a requisição.
    """
    available = getattr(item, "available", None)
    if available is None:
        from inventory.services import available_quantity

        available = available_quantity(item)
    if available <= 0:
        return "none"
    if item.reorder_level > 0 and available <= item.reorder_level:
        return "low"
    return "in stock"
