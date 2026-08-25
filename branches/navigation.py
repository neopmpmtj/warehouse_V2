"""Branch landing cards and page header context (shared with warehouse dashboard)."""

from .capabilities import branch_role
from .services import get_active_memberships


def branch_dashboard_cards(*, include_picker=False):
    """Card links for branch staff landing pages."""
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
                "desc": "Read-only catalogue (cost hidden)",
                "url": "/branch/catalog/",
            },
            {
                "title_key": "cardRequisicao",
                "desc_key": "cardRequisicaoDesc",
                "title": "Requisição interna",
                "desc": "Request stock from the warehouse",
                "url": "/branch/requests/",
            },
            {
                "title_key": "cardBranchThreads",
                "desc_key": "cardBranchThreadsDesc",
                "title": "Branch threads",
                "desc": "Request items not in the catalogue",
                "url": "/branch/threads/",
            },
            {
                "title_key": "cardBranchReceipts",
                "desc_key": "cardBranchReceiptsDesc",
                "title": "Branch receipts",
                "desc": "Receive goods and view branch stock",
                "url": "/branch/receipts/",
            },
            {
                "title_key": "cardCompanyVoice",
                "desc_key": "cardCompanyVoiceDesc",
                "title": "Company Voice",
                "desc": "Suggestions, praise, and concerns — all logged-in staff can read and post.",
                "url": "/company-voice/",
            },
        ]
    )
    return cards


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
