"""Thread capability checks for the website.

The ``threads`` app deliberately has NO Django model permissions: warehouse
groups only sync perms for ``products, procurement, inventory, orders``
(``accounts/groups.py`` ``CATALOG_APP_LABELS``), so gating must be
capability-based. Do NOT add ``threads`` to ``sync_warehouse_groups``.
"""

from accounts.authz import user_is_active
from accounts.groups import GROUP_ADMINS, warehouse_group_name
from branches.capabilities import ROLE_ADMIN, ROLE_MANAGER, branch_role


def is_warehouse_staff(user):
    """Any active warehouse group member can see/post on the warehouse side."""
    if not user_is_active(user):
        return False
    return warehouse_group_name(user) is not None


def can_force_close_thread(user, thread):
    """Override-close: branch manager/admin of that branch, or warehouse admin.

    Mirrors ``can_adjust_stock`` for the warehouse side; checks the *closer's*
    role, never the opener's (a deactivated opener must not block a close).
    """
    if not user_is_active(user):
        return False
    if getattr(user, "is_superuser", False):
        return True
    if warehouse_group_name(user) == GROUP_ADMINS:
        return True
    if thread is not None:
        return branch_role(user, thread.branch) in (ROLE_MANAGER, ROLE_ADMIN)
    return False
