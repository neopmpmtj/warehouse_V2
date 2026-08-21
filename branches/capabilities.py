"""Branch capability checks for the website (mirror accounts/capabilities.py)."""

from accounts.authz import user_is_active

from .models import BranchMembership

ROLE_OPERATOR = BranchMembership.Role.OPERATOR
ROLE_MANAGER = BranchMembership.Role.MANAGER
ROLE_ADMIN = BranchMembership.Role.ADMIN


def branch_role(user, branch):
    """Return the user's role on `branch`, or None if not a member."""
    if not user_is_active(user) or branch is None:
        return None
    membership = BranchMembership.objects.filter(user=user, branch=branch).first()
    return membership.role if membership else None


def is_branch_member(user):
    """True if the user holds at least one branch membership."""
    if not user_is_active(user):
        return False
    return BranchMembership.objects.filter(user=user).exists()


def can_draft_request(user, branch):
    """Any role may draft lines, submit, or cancel a draft request."""
    return branch_role(user, branch) is not None


def can_approve_request(user, branch):
    """Manager (capped) and admin (unlimited) approve / reject / cancel-approved."""
    return branch_role(user, branch) in (ROLE_MANAGER, ROLE_ADMIN)
