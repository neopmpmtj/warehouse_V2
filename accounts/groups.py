from django.contrib.auth.models import Group, Permission

GROUP_ADMINS = "warehouse_admins"
GROUP_MANAGERS = "warehouse_managers"
GROUP_OPERATORS = "warehouse_data_operators"

WAREHOUSE_GROUP_NAMES = (GROUP_ADMINS, GROUP_MANAGERS, GROUP_OPERATORS)
LEGACY_WAREHOUSE_GROUP_NAME = "Warehouse"

CATALOG_MODELS = ("item", "familyproduct", "supplier", "supplieritemprice", "purchaseorder", "goodsreceipt")
CATALOG_NO_DELETE_MODELS = ("goodsreceipt",)
CATALOG_VIEW_ONLY_MODELS = (
    "vatrate",
    "itemchangelog",
    "familychangelog",
    "supplierchangelog",
    "supplieritempricechangelog",
    "purchaseorderchangelog",
    "goodsreceiptline",
    "stockmovement",
)

VIEW_ITEM = "products.view_item"
ADD_ITEM = "products.add_item"
CHANGE_ITEM = "products.change_item"
DELETE_ITEM = "products.delete_item"
ADD_FAMILY = "products.add_familyproduct"
CHANGE_FAMILY = "products.change_familyproduct"
DELETE_FAMILY = "products.delete_familyproduct"
ADD_SUPPLIER = "products.add_supplier"
CHANGE_SUPPLIER = "products.change_supplier"
DELETE_SUPPLIER = "products.delete_supplier"
ADD_SUPPLIER_ITEM_PRICE = "products.add_supplieritemprice"
CHANGE_SUPPLIER_ITEM_PRICE = "products.change_supplieritemprice"
APPROVE_PURCHASE_ORDER = "procurement.can_approve"

WAREHOUSE_USERS = (
    ("warehouse.admin@centcompras.dev", GROUP_ADMINS),
    ("warehouse.manager@centcompras.dev", GROUP_MANAGERS),
    ("warehouse.operator@centcompras.dev", GROUP_OPERATORS),
)


def _codenames_for_group(group_name):
    view = [f"view_{model}" for model in CATALOG_MODELS]
    view.extend(f"view_{model}" for model in CATALOG_VIEW_ONLY_MODELS)
    add = [f"add_{model}" for model in CATALOG_MODELS]
    change = [f"change_{model}" for model in CATALOG_MODELS]
    delete = [f"delete_{model}" for model in CATALOG_MODELS if model not in CATALOG_NO_DELETE_MODELS]
    if group_name == GROUP_ADMINS:
        return view + add + change + delete + ["can_approve", "can_adjust_stock"]
    if group_name == GROUP_MANAGERS:
        return view + add + change
    return view


CATALOG_APP_LABELS = ("products", "procurement", "inventory")


def _catalog_permissions(codenames):
    return Permission.objects.filter(
        content_type__app_label__in=CATALOG_APP_LABELS,
        codename__in=codenames,
    )


def sync_warehouse_groups():
    """Replace each warehouse group's permissions with the code-defined set.

    These three groups are fully managed in code. Extra permissions added in
    /admin/ are wiped on migrate. Do not grant extras on warehouse groups.
    """
    for group_name in WAREHOUSE_GROUP_NAMES:
        group, _ = Group.objects.get_or_create(name=group_name)
        desired = set(_catalog_permissions(_codenames_for_group(group_name)))
        if set(group.permissions.all()) != desired:
            group.permissions.set(desired)


def ensure_warehouse_groups(sender, **kwargs):
    if getattr(sender, "name", None) not in ("products", "procurement", "inventory"):
        return
    sync_warehouse_groups()


def clear_permission_cache(user):
    for cache_name in ("_perm_cache", "_user_perm_cache", "_group_perm_cache"):
        if hasattr(user, cache_name):
            delattr(user, cache_name)


def assign_warehouse_group(user, group_name=GROUP_ADMINS):
    if group_name not in WAREHOUSE_GROUP_NAMES:
        raise ValueError(f"Unknown warehouse group: {group_name}")

    group = Group.objects.get(name=group_name)
    user.groups.remove(*Group.objects.filter(name__in=WAREHOUSE_GROUP_NAMES))
    user.groups.add(group)
    clear_permission_cache(user)
    return group
