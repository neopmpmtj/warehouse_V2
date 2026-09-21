from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.groups import (
    GROUP_ADMINS,
    GROUP_MANAGERS,
    GROUP_OPERATORS,
    assign_warehouse_group,
    set_warehouse_grade,
)
from branches.capabilities import ROLE_ADMIN, ROLE_MANAGER, ROLE_OPERATOR
from branches.services import SESSION_KEY, assign_membership, create_branch
from inventory.models import BranchWarehouseShipment
from inventory.services import (
    adjust_branch_stock,
    issue_goods,
    receive_from_branch,
    return_dispatch,
    send_to_warehouse,
    unread_alert_count,
)
from orders.models import InternalRequest
from orders.services import add_line, approve, create_internal_request, submit
from products.models import FamilyProduct, Item, VatRate
from threads.models import ThreadMessage
from threads.services import create_thread, mark_read, post_message, unread_thread_count

from .models import SectionCursor
from .services import (
    Section,
    mark_section_seen,
    unread_section_counts,
)


def _user(email):
    return get_user_model().objects.create_user(email=email, password="test-pass-123")


def _warehouse(email, group=GROUP_ADMINS, grade=1):
    user = _user(email)
    assign_warehouse_group(user, group)
    set_warehouse_grade(user, grade)
    return user


def _branch_user(email, branch, role):
    user = _user(email)
    assign_membership(user, branch, role)
    return user


def _item(description, quantity="10"):
    family = FamilyProduct.objects.create(name="Fam " + description, is_active=True)
    vat, _ = VatRate.objects.get_or_create(
        code="VAT14",
        defaults={"label": "14%", "rate": Decimal("0.14")},
    )
    return Item.objects.create(
        family=family,
        vat_rate=vat,
        description=description,
        internal_code=description.upper().replace(" ", "-")[:20],
        unit_of_measure=Item.UnitOfMeasure.PIECE,
        is_active=True,
        retail_price=Decimal("10.00"),
        wholesale_price=Decimal("5.00"),
        special_price=Decimal("8.00"),
        quantity=Decimal(quantity),
        reorder_level=Decimal("0"),
    )


def _seen(user, section, branch=None, seconds_ago=5):
    SectionCursor.objects.update_or_create(
        user=user,
        section=section,
        branch=branch,
        defaults={"last_seen_at": timezone.now() - timedelta(seconds=seconds_ago)},
    )


class InboxSectionTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.north = create_branch("North Inbox")
        self.south = create_branch("South Inbox")
        self.operator = _branch_user("inb-op@example.com", self.north, ROLE_OPERATOR)
        self.manager = _branch_user("inb-mgr@example.com", self.north, ROLE_MANAGER)
        self.admin = _branch_user("inb-adm@example.com", self.north, ROLE_ADMIN)
        self.south_mgr = _branch_user("inb-south@example.com", self.south, ROLE_MANAGER)
        self.wh_admin = _warehouse("inb-wh@example.com")
        self.wh_admin2 = _warehouse("inb-wh2@example.com")
        self.wh_op = _warehouse("inb-wh-op@example.com", GROUP_OPERATORS)
        self.wh_mgr_g2 = _warehouse("inb-wh-g2@example.com", GROUP_MANAGERS, 2)
        self.item = _item("Inbox Widget", quantity="20")

    def _login_branch(self, user, branch):
        self.client.force_login(user)
        session = self.client.session
        session[SESSION_KEY] = branch.id
        session.save()

    def _approved_request(self, branch=None, user=None, approver=None, qty="4"):
        branch = branch or self.north
        user = user or self.operator
        approver = approver or self.manager
        req = create_internal_request(branch, user)
        line = add_line(req, self.item, qty, user)
        req = submit(req, user)
        req = approve(req, approver)
        req.refresh_from_db()
        return req, line

    def test_missing_cursor_is_zero_despite_existing_queue(self):
        self._approved_request()
        counts = unread_section_counts(self.wh_admin)
        self.assertEqual(counts[Section.WAREHOUSE_REQUESTS], 0)

    def test_approve_after_visit_badges_requests(self):
        _seen(self.wh_admin, Section.WAREHOUSE_REQUESTS)
        self._approved_request()
        counts = unread_section_counts(self.wh_admin)
        self.assertEqual(counts[Section.WAREHOUSE_REQUESTS], 1)

    def test_draft_does_not_badge_warehouse(self):
        _seen(self.wh_admin, Section.WAREHOUSE_REQUESTS)
        create_internal_request(self.north, self.operator)
        counts = unread_section_counts(self.wh_admin)
        self.assertEqual(counts[Section.WAREHOUSE_REQUESTS], 0)

    def test_fulfilling_does_not_double_count(self):
        _seen(self.wh_admin, Section.WAREHOUSE_REQUESTS)
        req, line = self._approved_request(qty="10")
        self.assertEqual(unread_section_counts(self.wh_admin)[Section.WAREHOUSE_REQUESTS], 1)
        issue_goods(req, [{"line_id": line.id, "quantity_issued": "4"}], self.wh_admin)
        req.refresh_from_db()
        self.assertEqual(req.status, InternalRequest.Status.FULFILLING)
        self.assertEqual(unread_section_counts(self.wh_admin)[Section.WAREHOUSE_REQUESTS], 1)

    def test_ship_without_visiting_drops_count(self):
        _seen(self.wh_admin, Section.WAREHOUSE_REQUESTS)
        req, line = self._approved_request(qty="4")
        self.assertEqual(unread_section_counts(self.wh_admin)[Section.WAREHOUSE_REQUESTS], 1)
        issue_goods(req, [{"line_id": line.id, "quantity_issued": "4"}], self.wh_admin)
        req.refresh_from_db()
        self.assertEqual(req.status, InternalRequest.Status.SHIPPED)
        self.assertEqual(unread_section_counts(self.wh_admin)[Section.WAREHOUSE_REQUESTS], 0)

    def test_two_warehouse_users_independent(self):
        _seen(self.wh_admin, Section.WAREHOUSE_REQUESTS)
        _seen(self.wh_admin2, Section.WAREHOUSE_REQUESTS)
        self._approved_request()
        self.assertEqual(unread_section_counts(self.wh_admin)[Section.WAREHOUSE_REQUESTS], 1)
        self.assertEqual(unread_section_counts(self.wh_admin2)[Section.WAREHOUSE_REQUESTS], 1)
        mark_section_seen(self.wh_admin, Section.WAREHOUSE_REQUESTS)
        self.assertEqual(unread_section_counts(self.wh_admin)[Section.WAREHOUSE_REQUESTS], 0)
        self.assertEqual(unread_section_counts(self.wh_admin2)[Section.WAREHOUSE_REQUESTS], 1)

    def test_work_page_get_marks_seen_json_does_not(self):
        _seen(self.wh_admin, Section.WAREHOUSE_REQUESTS)
        self._approved_request()
        self.assertEqual(unread_section_counts(self.wh_admin)[Section.WAREHOUSE_REQUESTS], 1)
        self.client.force_login(self.wh_admin)
        listed = self.client.get(reverse("warehouse_request_list"))
        self.assertEqual(listed.status_code, 200)
        self.assertEqual(unread_section_counts(self.wh_admin)[Section.WAREHOUSE_REQUESTS], 1)
        page = self.client.get(reverse("internal_request_queue_console"))
        self.assertEqual(page.status_code, 200)
        self.assertEqual(unread_section_counts(self.wh_admin)[Section.WAREHOUSE_REQUESTS], 0)

    def test_dashboard_get_does_not_mark(self):
        _seen(self.wh_admin, Section.WAREHOUSE_REQUESTS)
        self._approved_request()
        self.client.force_login(self.wh_admin)
        response = self.client.get(reverse("staff_dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(unread_section_counts(self.wh_admin)[Section.WAREHOUSE_REQUESTS], 1)
        cards = response.context["warehouse_cards"]
        req_card = next(card for card in cards if card["url"] == "/manage/internal-requests/")
        self.assertEqual(req_card["unread"], 1)
        self.assertContains(response, 'class="dash-card-badge"')

    def test_inbound_send_receive(self):
        _seen(self.wh_admin, Section.WAREHOUSE_INBOUND)
        adjust_branch_stock(self.north, self.item, "8", "seed", self.admin)
        shipment = send_to_warehouse(
            self.north,
            [{"item_id": self.item.id, "quantity": "3"}],
            self.manager,
            reason="surplus",
        )
        self.assertEqual(shipment.status, BranchWarehouseShipment.Status.IN_TRANSIT)
        self.assertEqual(unread_section_counts(self.wh_admin)[Section.WAREHOUSE_INBOUND], 1)
        receive_from_branch(
            shipment,
            [{"line_id": shipment.lines.get().id, "quantity_received": "3"}],
            self.wh_admin,
            reason="arrived",
        )
        self.assertEqual(unread_section_counts(self.wh_admin)[Section.WAREHOUSE_INBOUND], 0)

    def test_inbound_work_page_marks_seen(self):
        _seen(self.wh_admin, Section.WAREHOUSE_INBOUND)
        adjust_branch_stock(self.north, self.item, "4", "seed", self.admin)
        send_to_warehouse(
            self.north,
            [{"item_id": self.item.id, "quantity": "2"}],
            self.manager,
            reason="surplus",
        )
        self.client.force_login(self.wh_admin)
        self.client.get(reverse("warehouse_inbound_console"))
        self.assertEqual(unread_section_counts(self.wh_admin)[Section.WAREHOUSE_INBOUND], 0)

    def test_dispatch_return_badges_returns_and_alerts(self):
        _seen(self.wh_admin, Section.WAREHOUSE_RETURNS)
        req, line = self._approved_request(qty="4")
        goods_issue = issue_goods(
            req, [{"line_id": line.id, "quantity_issued": "4"}], self.wh_admin
        )
        return_dispatch(goods_issue, self.manager, reason="damaged pallet")
        self.assertEqual(unread_section_counts(self.wh_admin)[Section.WAREHOUSE_RETURNS], 1)
        self.assertEqual(unread_alert_count(self.wh_admin), 1)
        self.assertEqual(unread_section_counts(self.wh_op)[Section.WAREHOUSE_RETURNS], 0)
        _seen(self.wh_op, Section.WAREHOUSE_RETURNS)
        self.assertEqual(unread_section_counts(self.wh_op)[Section.WAREHOUSE_RETURNS], 1)
        self.client.force_login(self.wh_op)
        op_dash = self.client.get(reverse("staff_dashboard"))
        op_cards = {card["url"]: card for card in op_dash.context["warehouse_cards"]}
        self.assertNotIn("/manage/alerts/", op_cards)
        self.assertEqual(op_cards["/manage/returned-dispatches/"]["unread"], 1)
        self.client.force_login(self.wh_admin)
        self.client.get(reverse("warehouse_returns_console"))
        self.assertEqual(unread_section_counts(self.wh_admin)[Section.WAREHOUSE_RETURNS], 0)
        self.assertEqual(unread_alert_count(self.wh_admin), 1)

    def test_goods_issue_badges_branch_receipts_only(self):
        _seen(self.manager, Section.BRANCH_RECEIPTS, branch=self.north)
        _seen(self.south_mgr, Section.BRANCH_RECEIPTS, branch=self.south)
        req, line = self._approved_request(qty="3")
        issue_goods(req, [{"line_id": line.id, "quantity_issued": "3"}], self.wh_admin)
        north = unread_section_counts(self.manager, branch=self.north)
        south = unread_section_counts(self.south_mgr, branch=self.south)
        self.assertEqual(north[Section.BRANCH_RECEIPTS], 1)
        self.assertEqual(south[Section.BRANCH_RECEIPTS], 0)
        self._login_branch(self.manager, self.north)
        dash = self.client.get(reverse("branch_dashboard"))
        self.assertEqual(dash.status_code, 200)
        receipts = next(
            card for card in dash.context["work_cards"] if card["url"] == "/branch/receipts/"
        )
        self.assertEqual(receipts["unread"], 1)
        self.client.get(reverse("branch_receipt_console"))
        self.assertEqual(
            unread_section_counts(self.manager, branch=self.north)[Section.BRANCH_RECEIPTS],
            0,
        )

    def test_returned_issue_leaves_receipts_inbox(self):
        _seen(self.manager, Section.BRANCH_RECEIPTS, branch=self.north)
        req, line = self._approved_request(qty="2")
        goods_issue = issue_goods(
            req, [{"line_id": line.id, "quantity_issued": "2"}], self.wh_admin
        )
        self.assertEqual(
            unread_section_counts(self.manager, branch=self.north)[Section.BRANCH_RECEIPTS],
            1,
        )
        return_dispatch(goods_issue, self.manager, reason="wrong site")
        self.assertEqual(
            unread_section_counts(self.manager, branch=self.north)[Section.BRANCH_RECEIPTS],
            0,
        )

    def test_thread_badge_not_cleared_by_list(self):
        thread = create_thread(
            self.north,
            self.operator,
            subject="Need a brass valve",
            first_message="Not in catalogue.",
        )
        self.assertEqual(unread_thread_count(self.wh_admin), 1)
        self.assertEqual(unread_thread_count(self.operator, branch=self.north), 0)
        self.client.force_login(self.wh_admin)
        page = self.client.get(reverse("warehouse_thread_console"))
        self.assertEqual(page.status_code, 200)
        self.assertEqual(unread_thread_count(self.wh_admin), 1)
        listed = self.client.get(reverse("warehouse_thread_list"))
        self.assertEqual(listed.status_code, 200)
        self.assertEqual(unread_thread_count(self.wh_admin), 1)
        dash = self.client.get(reverse("staff_dashboard"))
        threads_card = next(
            card for card in dash.context["warehouse_cards"] if card["url"] == "/manage/threads/"
        )
        self.assertEqual(threads_card["unread"], 1)
        mark_read(thread, self.wh_admin)
        self.assertEqual(unread_thread_count(self.wh_admin), 0)

    def test_thread_reply_badges_branch_dashboard(self):
        thread = create_thread(
            self.north,
            self.operator,
            subject="Need tape",
            first_message="Please source.",
        )
        post_message(thread, self.wh_admin, "On it.", ThreadMessage.Side.WAREHOUSE)
        self._login_branch(self.operator, self.north)
        dash = self.client.get(reverse("branch_dashboard"))
        threads_card = next(
            card
            for card in dash.context["communication_cards"]
            if card["url"] == "/branch/threads/"
        )
        self.assertEqual(threads_card["unread"], 1)
        self.assertIsNone(
            next(
                (
                    card.get("unread")
                    for card in dash.context["communication_cards"]
                    if card["url"] == "/company-voice/"
                ),
                None,
            )
        )
