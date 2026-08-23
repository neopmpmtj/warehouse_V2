"""Website capability checks: Django group perms plus warehouse grade."""

from accounts.authz import user_is_active
from accounts.groups import (
    ADD_FAMILY,
    ADD_ITEM,
    ADD_SUBFAMILY,
    ADD_SUPPLIER,
    ADD_SUPPLIER_ITEM_PRICE,
    APPROVE_PURCHASE_ORDER,
    CHANGE_FAMILY,
    CHANGE_ITEM,
    CHANGE_SUBFAMILY,
    CHANGE_SUPPLIER,
    CHANGE_SUPPLIER_ITEM_PRICE,
    GROUP_ADMINS,
    GROUP_MANAGERS,
    GROUP_OPERATORS,
    warehouse_group_name,
)

ADD_PO = "procurement.add_purchaseorder"
CHANGE_PO = "procurement.change_purchaseorder"
ADD_GOODS_RECEIPT = "inventory.add_goodsreceipt"
ADJUST_STOCK = "inventory.can_adjust_stock"
ISSUE_GOODS = "inventory.can_issue_goods"

MUTATE_PERMISSIONS = frozenset(
    {
        ADD_ITEM,
        CHANGE_ITEM,
        ADD_FAMILY,
        CHANGE_FAMILY,
        ADD_SUBFAMILY,
        CHANGE_SUBFAMILY,
        ADD_SUPPLIER,
        CHANGE_SUPPLIER,
        ADD_SUPPLIER_ITEM_PRICE,
        CHANGE_SUPPLIER_ITEM_PRICE,
        ADD_PO,
        CHANGE_PO,
        ADD_GOODS_RECEIPT,
    }
)


def _grade(user):
    return int(getattr(user, "warehouse_grade", 1) or 1)


def _is_warehouse_admin(user):
    if getattr(user, "is_superuser", False):
        return True
    return warehouse_group_name(user) == GROUP_ADMINS


def can_mutate_catalog(user):
    if not user_is_active(user):
        return False
    if _is_warehouse_admin(user):
        return True
    group = warehouse_group_name(user)
    if group == GROUP_MANAGERS:
        return True
    if group == GROUP_OPERATORS:
        return _grade(user) >= 2
    return False


def can_receive_goods(user):
    return can_mutate_catalog(user)


def can_issue_goods(user):
    """Same people as can_receive_goods (mutate closed circuit), own perm code."""
    return can_mutate_catalog(user)


def can_short_close_issue(user):
    """Warehouse short-close: manager grade 2+ or admin (not operators)."""
    return can_approve_purchase_order(user)


def can_approve_purchase_order(user):
    if not user_is_active(user):
        return False
    if _is_warehouse_admin(user):
        return True
    if warehouse_group_name(user) == GROUP_MANAGERS:
        return _grade(user) >= 2
    return False


def can_adjust_stock(user):
    if not user_is_active(user):
        return False
    return _is_warehouse_admin(user)


def can_edit_approval_policy(user):
    if not user_is_active(user):
        return False
    return _is_warehouse_admin(user)


def has_effective_perm(user, perm):
    """Coarse Django perm plus grade cut for mutate / approve / adjust."""
    if not user.has_perm(perm):
        return False
    if perm == APPROVE_PURCHASE_ORDER:
        return can_approve_purchase_order(user)
    if perm == ADJUST_STOCK:
        return can_adjust_stock(user)
    if perm == ISSUE_GOODS:
        return can_issue_goods(user)
    if perm in MUTATE_PERMISSIONS:
        return can_mutate_catalog(user)
    return True


def catalog_permission_flags(user):
    return {
        "add_item": has_effective_perm(user, ADD_ITEM),
        "change_item": has_effective_perm(user, CHANGE_ITEM),
        "add_family": has_effective_perm(user, ADD_FAMILY),
        "change_family": has_effective_perm(user, CHANGE_FAMILY),
        "add_sub_family": has_effective_perm(user, ADD_SUBFAMILY),
        "change_sub_family": has_effective_perm(user, CHANGE_SUBFAMILY),
        "add_supplier": has_effective_perm(user, ADD_SUPPLIER),
        "change_supplier": has_effective_perm(user, CHANGE_SUPPLIER),
        "add_supplier_item_price": has_effective_perm(user, ADD_SUPPLIER_ITEM_PRICE),
        "change_supplier_item_price": has_effective_perm(user, CHANGE_SUPPLIER_ITEM_PRICE),
    }


def procurement_permission_flags(user):
    return {
        "add_purchaseorder": has_effective_perm(user, ADD_PO),
        "change_purchaseorder": has_effective_perm(user, CHANGE_PO),
        "can_approve": has_effective_perm(user, APPROVE_PURCHASE_ORDER),
    }


def inventory_permission_flags(user):
    return {
        "add_goodsreceipt": has_effective_perm(user, ADD_GOODS_RECEIPT),
        "can_adjust_stock": has_effective_perm(user, ADJUST_STOCK),
        "can_issue_goods": has_effective_perm(user, ISSUE_GOODS),
        "can_short_close": can_short_close_issue(user),
    }
