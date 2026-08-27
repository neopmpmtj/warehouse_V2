from django.conf import settings
from django.shortcuts import render
from django.views.decorators.http import require_GET

from accounts.capabilities import can_edit_approval_policy
from accounts.groups import warehouse_group_name
from branches.navigation import branch_dashboard_cards
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
                "title_key": "cardItemConsole",
                "desc_key": "cardItemConsoleDesc",
                "title": "Item console",
                "desc": "Manage the catalogue: items, families, sub-families, suppliers, prices",
                "url": "/manage/items/",
            },
            {
                "title_key": "cardManagerCatalog",
                "desc_key": "cardManagerCatalogDesc",
                "title": "Manager catalog",
                "desc": "Stock + price view across the whole catalogue",
                "url": "/manage/catalog/",
            },
            {
                "title_key": "cardPurchaseOrders",
                "desc_key": "cardPurchaseOrdersDesc",
                "title": "Purchase orders",
                "desc": "Create, approve, receive and manage purchase orders",
                "url": "/manage/purchase-orders/",
            },
            {
                "title_key": "cardGoodsReceipts",
                "desc_key": "cardGoodsReceiptsDesc",
                "title": "Goods receipts & stock",
                "desc": "Receive goods, adjust stock, view stock movements",
                "url": "/manage/goods-receipts/",
            },
            {
                "title_key": "cardInternalRequests",
                "desc_key": "cardInternalRequestsDesc",
                "title": "Internal requests",
                "desc": "Warehouse queue: fulfil branch requisições and issue goods",
                "url": "/manage/internal-requests/",
            },
            {
                "title_key": "cardRequestThreads",
                "desc_key": "cardRequestThreadsDesc",
                "title": "Request threads",
                "desc": "Catalogue-gap requests from branches",
                "url": "/manage/threads/",
            },
        ]
        if can_edit_policy:
            warehouse_cards.append(
                {
                    "title_key": "cardPoLimits",
                    "desc_key": "cardPoLimitsDesc",
                    "title": "PO approval limits",
                    "desc": "Warehouse approval caps (admins only)",
                    "url": "/manage/approval-limits/",
                }
            )
            warehouse_cards.append(
                {
                    "title_key": "cardBranchLimits",
                    "desc_key": "cardBranchLimitsDesc",
                    "title": "Branch approval limits",
                    "desc": "Branch manager caps (admins only)",
                    "url": "/manage/branch-approval-limits/",
                }
            )
        if user.is_superuser:
            warehouse_cards.append(
                {
                    "title_key": "cardDjangoAdmin",
                    "desc_key": "cardDjangoAdminDesc",
                    "title": "Django admin",
                    "desc": "Site administration (superuser only)",
                    "url": "/admin/",
                }
            )

    branch_cards = []
    if has_branch:
        memberships = list(get_active_memberships(user))
        branch_cards = branch_dashboard_cards(include_picker=len(memberships) > 1)

    visualization_cards = []
    if is_warehouse:
        visualization_cards = [
            {
                "title_key": "cardCostTrends",
                "desc_key": "cardCostTrendsDesc",
                "title": "Cost trends",
                "desc": "Reference purchase cost over time (demo chart)",
                "url": "/manage/cost-trends/",
            },
        ]

    context = {
        "groups": groups,
        "is_warehouse": is_warehouse,
        "can_edit_policy": can_edit_policy,
        "has_branch": has_branch,
        "warehouse_cards": warehouse_cards,
        "branch_cards": branch_cards,
        "visualization_cards": visualization_cards,
    }
    if user.is_superuser or settings.DEBUG:
        context["permissions"] = sorted(user.get_all_permissions())
    return render(request, "products/dashboard.html", context)
