"""Branch landing cards and page header context (shared with warehouse dashboard)."""

from .capabilities import branch_role
from .services import get_active_memberships


def branch_work_cards(*, include_picker=False):
    """Operational cards: picker (optional), catalog, requisição, receipts."""
    cards = []
    if include_picker:
        cards.append(
            {
                "title_key": "cardBranchPicker",
                "desc_key": "cardBranchPickerDesc",
                "title": "Branch picker",
                "desc": "Switch the active branch",
                "url": "/branch/select/",
            }
        )
    cards.extend(
        [
            {
                "title_key": "cardBranchCatalog",
                "desc_key": "cardBranchCatalogDesc",
                "title": "Branch catalog",
                "desc": "Read-only catalogue (cost always hidden; selling prices only in priced mode)",
                "url": "/branch/catalog/",
            },
            {
                "title_key": "cardRequisicao",
                "desc_key": "cardRequisicaoDesc",
                "title": "Internal request",
                "desc": "Request stock from the warehouse",
                "url": "/branch/requests/",
            },
            {
                "title_key": "cardBranchReceipts",
                "desc_key": "cardBranchReceiptsDesc",
                "title": "Branch receipts",
                "desc": "Receive goods against a dispatch",
                "url": "/branch/receipts/",
            },
            {
                "title_key": "cardBranchStock",
                "desc_key": "cardBranchStockDesc",
                "title": "Branch stock",
                "desc": "On-hand quantity for this branch",
                "url": "/branch/stock/",
            },
            {
                "title_key": "cardBranchConsume",
                "desc_key": "cardBranchConsumeDesc",
                "title": "Consume",
                "desc": "Take items off this branch's stock",
                "url": "/branch/consumption/",
            },
            {
                "title_key": "cardSendToWarehouse",
                "desc_key": "cardSendToWarehouseDesc",
                "title": "Send to warehouse",
                "desc": "Send surplus on-hand items to the warehouse",
                "url": "/branch/send-to-warehouse/",
            },
        ]
    )
    return cards


def branch_communication_cards(*, include_alerts=False, alerts_unread=0):
    """Messaging cards: optional Alerts, then threads, then Parle."""
    cards = []
    if include_alerts:
        cards.append(
            {
                "title_key": "cardAlerts",
                "desc_key": "cardAlertsDesc",
                "title": "Alerts",
                "desc": "Receipt discrepancies",
                "url": "/branch/alerts/",
                "unread": alerts_unread,
            }
        )
    cards.extend(
        [
            {
                "title_key": "cardBranchThreads",
                "desc_key": "cardBranchThreadsDesc",
                "title": "Branch threads",
                "desc": "Request items not in the catalogue",
                "url": "/branch/threads/",
            },
            {
                "title_key": "cardCompanyVoice",
                "desc_key": "cardCompanyVoiceDesc",
                "title": "Parle",
                "desc": "Suggestions, praise, and concerns — all logged-in staff can read and post.",
                "url": "/company-voice/",
            },
        ]
    )
    return cards


def branch_dashboard_cards(*, include_picker=False):
    """Card links for branch staff landing pages (warehouse dashboard uses the flat list)."""
    return branch_work_cards(include_picker=include_picker) + branch_communication_cards()


def branch_page_context(request):
    """Shared template context for branch work pages."""
    memberships = list(get_active_memberships(request.user))
    branch = request.active_branch
    role = branch_role(request.user, branch) if branch else None
    role_labels = {
        "operator": "Operator",
        "manager": "Manager",
        "admin": "Admin",
    }
    return {
        "branch": branch,
        "can_switch_branch": len(memberships) > 1,
        "branch_role": role,
        "branch_role_label": role_labels.get(role, role or ""),
    }
