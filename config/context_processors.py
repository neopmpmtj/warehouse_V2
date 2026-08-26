"""Template context processors (help-manual mapping)."""
from django.urls import resolve

# url_name -> user-manual basename (without extension).
HELP_MANUAL_BY_URL_NAME = {
    "staff_dashboard": "01-items",
    "item_console": "01-items",
    "catalog_console": "07-manager-catalog",
    "purchase_order_console": "02-purchase-orders",
    "goods_receipt_console": "03-goods-receipts",
    "internal_request_queue_console": "04-internal-requests",
    "warehouse_thread_console": "08-request-threads",
    "company_voice_feed": "09-company-voice",
    "approval_limit_console": "10-approval-limits",
    "branch_approval_limit_console": "10-approval-limits",
    "branch_select": "04-internal-requests",
    "branch_dashboard": "04-internal-requests",
    "branch_catalog": "04-internal-requests",
    "request_console": "04-internal-requests",
    "branch_receipt_console": "04-internal-requests",
    "branch_thread_console": "08-request-threads",
}
DEFAULT_HELP_MANUAL = "01-items"


def help_manual(request):
    """Expose the user-manual basename matching the current page, if known."""
    slug = DEFAULT_HELP_MANUAL
    try:
        match = request.resolver_match
        if match is not None and match.url_name:
            slug = HELP_MANUAL_BY_URL_NAME.get(match.url_name, DEFAULT_HELP_MANUAL)
    except Exception:  # noqa: BLE001 - never break rendering for a help link
        pass
    return {"help_manual_slug": slug}
