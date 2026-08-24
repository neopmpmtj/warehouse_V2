from django.conf import settings
from django.shortcuts import render
from django.views.decorators.http import require_GET

from accounts.capabilities import can_edit_approval_policy
from accounts.groups import warehouse_group_name
from branches.services import get_active_memberships

from .permissions import catalog_required


@catalog_required
@require_GET
def staff_dashboard(request):
    user = request.user
    groups = list(user.groups.order_by("name").values_list("name", flat=True))
    is_warehouse = user.is_superuser or warehouse_group_name(user) is not None
    can_edit_policy = can_edit_approval_policy(user)
    has_branch = get_active_memberships(user).exists()

    warehouse_cards = []
    if is_warehouse:
        warehouse_cards = [
            {
                "title": "Item console",
                "desc": "Manage the catalogue: items, families, sub-families, suppliers, prices",
                "url": "/manage/items/",
            },
            {
                "title": "Manager catalog",
                "desc": "Stock + price view across the whole catalogue",
                "url": "/manage/catalog/",
            },
            {
                "title": "Purchase orders",
                "desc": "Create, approve, receive and manage purchase orders",
                "url": "/manage/purchase-orders/",
            },
            {
                "title": "Goods receipts & stock",
                "desc": "Receive goods, adjust stock, view stock movements",
                "url": "/manage/goods-receipts/",
            },
            {
                "title": "Internal requests",
                "desc": "Warehouse queue: fulfil branch requisições and issue goods",
                "url": "/manage/internal-requests/",
            },
            {
                "title": "Request threads",
                "desc": "Catalogue-gap requests from branches",
                "url": "/manage/threads/",
            },
        ]
        if can_edit_policy:
            warehouse_cards.append(
                {
                    "title": "PO approval limits",
                    "desc": "Warehouse approval caps (admins only)",
                    "url": "/manage/approval-limits/",
                }
            )
            warehouse_cards.append(
                {
                    "title": "Branch approval limits",
                    "desc": "Branch manager caps (admins only)",
                    "url": "/manage/branch-approval-limits/",
                }
            )
        if user.is_superuser:
            warehouse_cards.append(
                {
                    "title": "Django admin",
                    "desc": "Site administration (superuser only)",
                    "url": "/admin/",
                }
            )

    branch_cards = []
    if has_branch:
        branch_cards = [
            {
                "title": "Branch picker",
                "desc": "Switch the active branch",
                "url": "/branch/select/",
            },
            {
                "title": "Branch catalog",
                "desc": "Read-only catalogue (cost hidden)",
                "url": "/branch/catalog/",
            },
            {
                "title": "Requisição interna",
                "desc": "Request stock from the warehouse",
                "url": "/branch/requests/",
            },
            {
                "title": "Branch threads",
                "desc": "Request items not in the catalogue",
                "url": "/branch/threads/",
            },
            {
                "title": "Branch receipts",
                "desc": "Receive goods and view branch stock",
                "url": "/branch/receipts/",
            },
        ]

    context = {
        "groups": groups,
        "is_warehouse": is_warehouse,
        "can_edit_policy": can_edit_policy,
        "has_branch": has_branch,
        "warehouse_cards": warehouse_cards,
        "branch_cards": branch_cards,
    }
    if user.is_superuser or settings.DEBUG:
        context["permissions"] = sorted(user.get_all_permissions())
    return render(request, "products/dashboard.html", context)
