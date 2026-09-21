from django.utils import timezone

from inventory.models import BranchWarehouseShipment, DispatchReturn
from inventory.services import (
    get_branch_goods_issues,
    get_branch_issue_summary,
    get_dispatch_returns,
    get_warehouse_inbound_shipments,
    unread_alert_count,
)
from orders.models import InternalRequest
from threads.services import unread_thread_count

from .models import SectionCursor

Section = SectionCursor.Section

CARD_URL_TO_BADGE = {
    "/manage/internal-requests/": Section.WAREHOUSE_REQUESTS,
    "/manage/incoming-from-branches/": Section.WAREHOUSE_INBOUND,
    "/manage/returned-dispatches/": Section.WAREHOUSE_RETURNS,
    "/manage/threads/": "threads",
    "/manage/alerts/": "alerts",
    "/branch/receipts/": Section.BRANCH_RECEIPTS,
    "/branch/threads/": "threads",
    "/branch/alerts/": "alerts",
}


def mark_section_seen(user, section, branch=None):
    """Advance the user's watermark for a work-queue page (HTML GET)."""
    SectionCursor.objects.update_or_create(
        user=user,
        section=section,
        branch=branch,
        defaults={"last_seen_at": timezone.now()},
    )


def unread_section_counts(user, branch=None):
    """New documents since this user's last visit. Missing cursor → 0."""
    counts = {
        Section.WAREHOUSE_REQUESTS: _count_qs(
            user,
            Section.WAREHOUSE_REQUESTS,
            InternalRequest.objects.filter(
                status__in=[
                    InternalRequest.Status.APPROVED,
                    InternalRequest.Status.FULFILLING,
                ]
            ),
            "approved_at",
        ),
        Section.WAREHOUSE_INBOUND: _count_qs(
            user,
            Section.WAREHOUSE_INBOUND,
            get_warehouse_inbound_shipments(status=BranchWarehouseShipment.Status.IN_TRANSIT),
            "sent_at",
        ),
        Section.WAREHOUSE_RETURNS: _count_qs(
            user,
            Section.WAREHOUSE_RETURNS,
            get_dispatch_returns(status=DispatchReturn.Status.IN_TRANSIT),
            "returned_at",
        ),
    }
    if branch is not None:
        counts[Section.BRANCH_RECEIPTS] = _count_open_branch_issues(user, branch)
    return counts


def dashboard_badges(user, branch=None):
    """Section watermarks + existing Alerts presence + Threads cursors."""
    badges = unread_section_counts(user, branch=branch)
    badges["alerts"] = unread_alert_count(user, branch=branch)
    badges["threads"] = unread_thread_count(user, branch=branch)
    return badges


def apply_dashboard_unread(cards, badges):
    """Set card['unread'] when the mapped section has a positive count."""
    for card in cards:
        key = CARD_URL_TO_BADGE.get(card.get("url"))
        if not key:
            continue
        count = badges.get(key) or 0
        if count:
            card["unread"] = count
        else:
            card.pop("unread", None)


def _cursor_since(user, section, branch=None):
    qs = SectionCursor.objects.filter(user=user, section=section)
    if branch is None:
        qs = qs.filter(branch__isnull=True)
    else:
        qs = qs.filter(branch=branch)
    row = qs.only("last_seen_at").first()
    return row.last_seen_at if row else None


def _count_qs(user, section, queryset, field, branch=None):
    since = _cursor_since(user, section, branch=branch)
    if since is None:
        return 0
    return queryset.filter(**{f"{field}__gt": since}).count()


def _count_open_branch_issues(user, branch):
    since = _cursor_since(user, Section.BRANCH_RECEIPTS, branch=branch)
    if since is None:
        return 0
    count = 0
    for goods_issue in get_branch_goods_issues(branch).filter(issued_at__gt=since):
        summary = get_branch_issue_summary(goods_issue)
        if any(int(row["remaining"]) > 0 for row in summary):
            count += 1
    return count
