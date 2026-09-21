from django.conf import settings
from django.contrib.auth.views import redirect_to_login
from django.shortcuts import redirect, render
from django.views.decorators.http import require_GET

from accounts.authz import deny_if_inactive
from accounts.capabilities import can_approve_purchase_order, can_edit_approval_policy
from accounts.groups import warehouse_group_name
from branches.navigation import branch_dashboard_cards
from branches.services import BRANCH_SELECT_URL, get_active_memberships, post_login_landing
from inbox.services import apply_dashboard_unread, dashboard_badges

from .permissions import can_view_catalog


@require_GET
def staff_dashboard(request):
    inactive = deny_if_inactive(request)
    if inactive is not None:
        return inactive
    if not request.user.is_authenticated:
        return redirect_to_login(request.get_full_path())
    if not can_view_catalog(request.user):
        landing = post_login_landing(request) or BRANCH_SELECT_URL
        if landing in ("/", request.path):
            landing = BRANCH_SELECT_URL
        return redirect(landing)

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
                "title_key": "cardIncomingFromBranches",
                "desc_key": "cardIncomingFromBranchesDesc",
                "title": "Incoming from branches",
                "desc": "Confirm items a branch sent to the warehouse",
                "url": "/manage/incoming-from-branches/",
            },
            {
                "title_key": "cardReturnedDispatches",
                "desc_key": "cardReturnedDispatchesDesc",
                "title": "Returned dispatches",
                "desc": "Restock or write off dispatches a branch sent back",
                "url": "/manage/returned-dispatches/",
            },
            {
                "title_key": "cardStockAtBranches",
                "desc_key": "cardStockAtBranchesDesc",
                "title": "Stock at branches",
                "desc": "Read-only on-hand quantity at every branch",
                "url": "/manage/stock-at-branches/",
            },
            {
                "title_key": "cardRequestThreads",
                "desc_key": "cardRequestThreadsDesc",
                "title": "Request threads",
                "desc": "Catalogue-gap requests from branches",
                "url": "/manage/threads/",
            },
        ]
        if can_approve_purchase_order(user):
            warehouse_cards.append(
                {
                    "title_key": "cardAlerts",
                    "desc_key": "cardAlertsDesc",
                    "title": "Alerts",
                    "desc": "Receipt discrepancies and dispatch returns",
                    "url": "/manage/alerts/",
                }
            )
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
    active_branch = getattr(request, "active_branch", None)
    if has_branch:
        memberships = list(get_active_memberships(user))
        branch_cards = branch_dashboard_cards(include_picker=len(memberships) > 1)
        if active_branch is not None:
            apply_dashboard_unread(branch_cards, dashboard_badges(user, branch=active_branch))
    if is_warehouse:
        apply_dashboard_unread(warehouse_cards, dashboard_badges(user))

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
