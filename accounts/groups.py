from django.contrib.admin.sites import AdminSite
from django.contrib.auth.models import Group, Permission

GROUP_ADMINS = "warehouse_admins"
GROUP_MANAGERS = "warehouse_managers"
GROUP_OPERATORS = "warehouse_data_operators"

WAREHOUSE_GROUP_NAMES = (GROUP_ADMINS, GROUP_MANAGERS, GROUP_OPERATORS)
LEGACY_WAREHOUSE_GROUP_NAME = "Warehouse"

CATALOG_MODELS = ("item", "familyproduct", "supplier")
CATALOG_VIEW_ONLY_MODELS = (
    "vatrate",
    "itemchangelog",
    "familychangelog",
    "supplierchangelog",
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
    delete = [f"delete_{model}" for model in CATALOG_MODELS]
    if group_name == GROUP_ADMINS:
        return view + add + change + delete
    if group_name == GROUP_MANAGERS:
        return view + add + change
    return view


def _products_permissions(codenames):
    return Permission.objects.filter(
        content_type__app_label="products",
        codename__in=codenames,
    )


def sync_warehouse_groups():
    Group.objects.filter(name=LEGACY_WAREHOUSE_GROUP_NAME).delete()

    for group_name in WAREHOUSE_GROUP_NAMES:
        group, _ = Group.objects.get_or_create(name=group_name)
        permissions = list(_products_permissions(_codenames_for_group(group_name)))
        if permissions:
            group.permissions.set(permissions)


def ensure_warehouse_groups(sender, **kwargs):
    if getattr(sender, "name", None) != "products":
        return
    sync_warehouse_groups()


def clear_permission_cache(user):
    for cache_name in ("_perm_cache", "_user_perm_cache", "_group_perm_cache"):
        if hasattr(user, cache_name):
            delattr(user, cache_name)


def assign_warehouse_group(user, group_name=GROUP_ADMINS):
    if group_name not in WAREHOUSE_GROUP_NAMES:
        raise ValueError(f"Unknown warehouse group: {group_name}")

    sync_warehouse_groups()
    group = Group.objects.get(name=group_name)
    user.groups.add(group)
    clear_permission_cache(user)
    return group


def restrict_admin_to_superusers():
    def has_permission(self, request):
        return bool(request.user.is_active and request.user.is_superuser)

    AdminSite.has_permission = has_permission
