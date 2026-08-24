import json
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.groups import GROUP_ADMINS, GROUP_MANAGERS, GROUP_OPERATORS, assign_warehouse_group, set_warehouse_grade
from branches.capabilities import ROLE_ADMIN, ROLE_MANAGER, ROLE_OPERATOR
from branches.models import Branch
from branches.services import SESSION_KEY, assign_membership, create_branch
from products.models import FamilyProduct, Item, VatRate

from .models import ItemRequestThread, ThreadMessage, ThreadReadState
from .services import (
    ClosePermissionDeniedError,
    CloseReasonRequiredError,
    CloseReasonTextRequiredError,
    InactiveBranchError,
    InvalidSatisfactionError,
    ItemNotFoundError,
    NotBranchMemberError,
    ThreadClosedError,
    close_thread,
    create_thread,
    link_items,
    post_message,
)


def _make_user(email):
    return get_user_model().objects.create_user(email=email, password="test-pass-123")


def _make_branch_user(email, branch, role):
    user = _make_user(email)
    assign_membership(user, branch, role)
    return user


def _make_warehouse_user(email, group=GROUP_ADMINS, grade=1):
    user = _make_user(email)
    assign_warehouse_group(user, group)
    set_warehouse_grade(user, grade)
    return user


def _make_item(description, active=True):
    family = FamilyProduct.objects.create(name="Fam " + description, is_active=True)
    vat = VatRate.objects.get(code="VAT16")
    return Item.objects.create(
        family=family,
        vat_rate=vat,
        description=description,
        internal_code=description.upper()[:20],
        unit_of_measure=Item.UnitOfMeasure.PIECE,
        is_active=active,
    )


class ThreadServiceTests(TestCase):
    def setUp(self):
        self.north = create_branch("North")
        self.south = create_branch("South")
        self.opener = _make_branch_user("opener@north.dev", self.north, ROLE_OPERATOR)
        self.branch_manager = _make_branch_user("manager@north.dev", self.north, ROLE_MANAGER)
        self.branch_admin = _make_branch_user("admin@north.dev", self.north, ROLE_ADMIN)
        self.other_branch = _make_branch_user("op@other.dev", self.south, ROLE_OPERATOR)
        self.wh_admin = _make_warehouse_user("wh.admin@dev.com", GROUP_ADMINS)
        self.wh_manager = _make_warehouse_user("wh.manager@dev.com", GROUP_MANAGERS, 2)

    def _thread(self, **kwargs):
        defaults = dict(
            branch=self.north,
            opened_by=self.opener,
            subject="Need a 25mm brass valve",
            first_message="Not in catalogue. Please source it.",
        )
        defaults.update(kwargs)
        return create_thread(**defaults)

    def test_create_sets_awaiting_warehouse_with_first_message(self):
        thread = self._thread()
        self.assertEqual(thread.status, ItemRequestThread.Status.AWAITING_WAREHOUSE)
        self.assertEqual(thread.message_count, 1)
        msg = thread.messages.get()
        self.assertEqual(msg.side, ThreadMessage.Side.BRANCH)
        self.assertEqual(msg.author, self.opener)
        self.assertEqual(msg.body, "Not in catalogue. Please source it.")
        self.assertTrue(thread.change_logs.filter(action="created").exists())

    def test_create_requires_subject_and_body(self):
        with self.assertRaises(ValidationError):
            self._thread(subject="   ")
        with self.assertRaises(ValidationError):
            self._thread(first_message="")

    def test_create_requires_active_branch(self):
        self.north.is_active = False
        self.north.save()
        with self.assertRaises(InactiveBranchError):
            self._thread()

    def test_post_flips_state(self):
        thread = self._thread()
        # warehouse replies -> awaiting_branch
        post_message(thread, self.wh_admin, "We can source that.", ThreadMessage.Side.WAREHOUSE)
        thread.refresh_from_db()
        self.assertEqual(thread.status, ItemRequestThread.Status.AWAITING_BRANCH)
        self.assertEqual(thread.message_count, 2)
        # branch replies -> awaiting_warehouse
        post_message(thread, self.opener, "Great, please order 10.", ThreadMessage.Side.BRANCH)
        thread.refresh_from_db()
        self.assertEqual(thread.status, ItemRequestThread.Status.AWAITING_WAREHOUSE)
        # two warehouse replies in a row stay awaiting_branch
        post_message(thread, self.wh_admin, "Will confirm.", ThreadMessage.Side.WAREHOUSE)
        post_message(thread, self.wh_manager, "Order placed.", ThreadMessage.Side.WAREHOUSE)
        thread.refresh_from_db()
        self.assertEqual(thread.status, ItemRequestThread.Status.AWAITING_BRANCH)

    def test_post_to_closed_thread_raises(self):
        thread = self._thread()
        close_thread(thread, self.opener, "request_satisfied")
        thread.refresh_from_db()
        with self.assertRaises(ThreadClosedError):
            post_message(thread, self.wh_admin, "Too late.", ThreadMessage.Side.WAREHOUSE)

    def test_close_opener_only(self):
        thread = self._thread()
        with self.assertRaises(ClosePermissionDeniedError):
            close_thread(thread, self.other_branch, "request_satisfied")
        # a plain operator from the SAME branch is not the opener -> denied
        same_branch_op = _make_branch_user("op2@north.dev", self.north, ROLE_OPERATOR)
        with self.assertRaises(ClosePermissionDeniedError):
            close_thread(thread, same_branch_op, "request_satisfied")
        # warehouse manager (not admin) cannot override
        with self.assertRaises(ClosePermissionDeniedError):
            close_thread(thread, self.wh_manager, "request_satisfied")
        # opener closes
        closed = close_thread(thread, self.opener, "request_satisfied")
        self.assertEqual(closed.status, ItemRequestThread.Status.CLOSED)
        self.assertEqual(closed.closed_by, self.opener)
        self.assertEqual(closed.close_reason, "request_satisfied")

    def test_override_close_matrix(self):
        thread = self._thread()
        # branch manager and admin override
        for closer in (self.branch_manager, self.branch_admin, self.wh_admin):
            fresh = self._thread(subject=f"override by {closer.email}")
            closed = close_thread(fresh, closer, "other", "Force closed — duplicate request.")
            self.assertEqual(closed.status, ItemRequestThread.Status.CLOSED)
            self.assertEqual(closed.closed_by, closer)
            self.assertEqual(closed.close_reason, "other")
            self.assertEqual(closed.close_reason_text, "Force closed — duplicate request.")
            log = closed.change_logs.get(action="closed")
            self.assertTrue(log.changes.get("override"))
            self.assertIsNone(closed.satisfaction)
            self.assertIsNone(log.changes.get("satisfaction"))
            self.assertEqual(log.reason, "Force closed — duplicate request.")

    def test_deactivated_opener_does_not_block_override(self):
        thread = self._thread()
        self.opener.is_active = False
        self.opener.save()
        closed = close_thread(thread, self.branch_manager, "other", "Opener left the company.")
        self.assertEqual(closed.status, ItemRequestThread.Status.CLOSED)

    def test_close_reason_rules(self):
        thread = self._thread()
        with self.assertRaises(CloseReasonRequiredError):
            close_thread(thread, self.opener, "")
        with self.assertRaises(CloseReasonRequiredError):
            close_thread(thread, self.opener, "something_invalid")
        with self.assertRaises(CloseReasonTextRequiredError):
            close_thread(thread, self.opener, "other", "   ")
        closed = close_thread(thread, self.opener, "other", "Wrote a proper reason")
        self.assertEqual(closed.close_reason_text, "Wrote a proper reason")

    def test_satisfaction_defaults_to_one_star(self):
        thread = self._thread()
        closed = close_thread(thread, self.opener, "request_satisfied")
        self.assertEqual(closed.satisfaction, 1)
        log = closed.change_logs.get(action="closed")
        self.assertEqual(log.changes.get("satisfaction"), 1)

    def test_satisfaction_editable_1_to_5(self):
        thread = self._thread()
        closed = close_thread(thread, self.opener, "request_satisfied", satisfaction=5)
        self.assertEqual(closed.satisfaction, 5)
        with self.assertRaises(ValidationError):
            close_thread(self._thread(subject="bad low"), self.opener, "request_satisfied", satisfaction=0)
        with self.assertRaises(ValidationError):
            close_thread(self._thread(subject="bad high"), self.opener, "request_satisfied", satisfaction=6)
        with self.assertRaises(ValidationError):
            close_thread(self._thread(subject="bad str"), self.opener, "request_satisfied", satisfaction="abc")
        with self.assertRaises(InvalidSatisfactionError):
            close_thread(self._thread(subject="bad float"), self.opener, "request_satisfied", satisfaction=3.7)
        with self.assertRaises(InvalidSatisfactionError):
            close_thread(self._thread(subject="bad bool"), self.opener, "request_satisfied", satisfaction=True)

    def test_create_requires_branch_membership(self):
        with self.assertRaises(NotBranchMemberError):
            create_thread(
                self.north,
                self.other_branch,
                "South user opening North thread",
                "Should be rejected at the service layer.",
            )

    def test_link_items_rejects_unknown_ids_and_skips_relink_log(self):
        thread = self._thread()
        item = _make_item("Brass valve 25mm")
        with self.assertRaises(ItemNotFoundError):
            link_items(thread, self.wh_admin, [item.id, 999999])
        self.assertEqual(thread.items.count(), 0)
        link_items(thread, self.wh_admin, [item.id])
        self.assertEqual(thread.change_logs.filter(action="item_linked").count(), 1)
        link_items(thread, self.wh_admin, [item.id])
        self.assertEqual(thread.change_logs.filter(action="item_linked").count(), 1)

    def test_link_items_warehouse_only_and_after_close(self):
        thread = self._thread()
        item = _make_item("Brass valve 25mm")
        with self.assertRaises(ValidationError):
            link_items(thread, self.opener, [item.id])
        link_items(thread, self.wh_admin, [item.id])
        thread.refresh_from_db()
        self.assertIn(item, thread.items.all())
        self.assertTrue(thread.change_logs.filter(action="item_linked").exists())
        # linking after close is allowed
        close_thread(thread, self.opener, "request_satisfied")
        item2 = _make_item("Brass valve 32mm")
        link_items(thread, self.wh_manager, [item2.id])
        thread.refresh_from_db()
        self.assertIn(item2, thread.items.all())

    def test_mark_read_and_unread(self):
        thread = self._thread()
        self.assertFalse(thread.is_unread_for(self.opener))  # opener created it
        self.assertTrue(thread.is_unread_for(self.wh_admin))  # no read cursor
        post_message(thread, self.wh_admin, "Reply.", ThreadMessage.Side.WAREHOUSE)
        thread.refresh_from_db()
        self.assertTrue(thread.is_unread_for(self.opener))
        from .services import mark_read

        mark_read(thread, self.opener)
        thread = ItemRequestThread.objects.get(pk=thread.pk)
        self.assertFalse(thread.is_unread_for(self.opener))
        self.assertTrue(ThreadReadState.objects.filter(thread=thread, user=self.opener).exists())


class ThreadIsolationTests(TestCase):
    def setUp(self):
        self.north = create_branch("North")
        self.south = create_branch("South")
        self.opener = _make_branch_user("opener@north.dev", self.north, ROLE_OPERATOR)
        self.other = _make_branch_user("op@other.dev", self.south, ROLE_OPERATOR)
        self.wh_admin = _make_warehouse_user("wh.admin@dev.com", GROUP_ADMINS)
        self.thread = create_thread(
            self.north,
            self.opener,
            "Need a 25mm brass valve",
            "Not in catalogue. Please source it.",
        )

    def _login(self, user, branch=None):
        client = Client()
        client.force_login(user)
        if branch is not None:
            session = client.session
            session[SESSION_KEY] = branch.id
            session.save()
        return client

    def test_other_branch_gets_404(self):
        client = self._login(self.other, self.south)
        resp = client.get(f"/api/branch/threads/{self.thread.id}/")
        self.assertEqual(resp.status_code, 404)

    def test_own_branch_sees_thread(self):
        client = self._login(self.opener, self.north)
        resp = client.get("/api/branch/threads/")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(len(data["threads"]), 1)
        self.assertEqual(data["threads"][0]["id"], self.thread.id)

    def test_warehouse_sees_all_and_inactive_branch_threads(self):
        client = self._login(self.wh_admin)
        resp = client.get("/api/manage/threads/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.json()["threads"]), 1)
        self.north.is_active = False
        self.north.save()
        resp = client.get("/api/manage/threads/")
        data = resp.json()
        self.assertEqual(len(data["threads"]), 1)
        self.assertFalse(data["threads"][0]["branch_active"])

    def test_branch_user_blocked_from_manage(self):
        client = self._login(self.opener)
        resp = client.get("/api/manage/threads/")
        self.assertEqual(resp.status_code, 403)
        resp = client.get("/manage/threads/")
        self.assertEqual(resp.status_code, 403)

    def test_branch_can_post_with_explicit_side(self):
        client = self._login(self.opener, self.north)
        resp = client.post(
            f"/api/branch/threads/{self.thread.id}/post/",
            data=json.dumps({"body": "Please confirm quantity."}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 201)
        msg = ThreadMessage.objects.get(pk=resp.json()["message"]["id"])
        self.assertEqual(msg.side, ThreadMessage.Side.BRANCH)

    def test_warehouse_can_post(self):
        client = self._login(self.wh_admin)
        resp = client.post(
            f"/api/manage/threads/{self.thread.id}/post/",
            data=json.dumps({"body": "We can source it."}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 201)
        msg = ThreadMessage.objects.get(pk=resp.json()["message"]["id"])
        self.assertEqual(msg.side, ThreadMessage.Side.WAREHOUSE)

    def test_warehouse_admin_force_close_via_api(self):
        client = self._login(self.wh_admin)
        resp = client.post(
            f"/api/manage/threads/{self.thread.id}/close/",
            data=json.dumps({"close_reason": "other", "close_reason_text": "Duplicate request."}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        self.thread.refresh_from_db()
        self.assertEqual(self.thread.status, ItemRequestThread.Status.CLOSED)

    def test_create_thread_via_api(self):
        client = self._login(self.opener, self.north)
        resp = client.post(
            "/api/branch/threads/create/",
            data=json.dumps({"subject": "Another gap item", "first_message": "Need a 40mm pipe."}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(ItemRequestThread.objects.filter(subject="Another gap item").count(), 1)

    def test_console_pages_render(self):
        branch_client = self._login(self.opener, self.north)
        resp = branch_client.get("/branch/threads/")
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'id="settings-toggle"')
        self.assertContains(resp, "Catalog")
        self.assertContains(resp, "Switch branch")
        self.assertNotContains(resp, 'id="language-select"')
        self.assertNotContains(resp, 'id="theme-toggle"')
        wh_client = self._login(self.wh_admin)
        resp = wh_client.get("/manage/threads/")
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'id="settings-toggle"')
        self.assertContains(resp, "Dashboard")
        self.assertNotContains(resp, 'id="language-select"')
        self.assertNotContains(resp, 'id="theme-toggle"')

    def test_post_vs_close_race_locked(self):
        """Concurrent-ish check: a post after a close in the same process must raise."""
        client = self._login(self.wh_admin)
        close_resp = client.post(
            f"/api/manage/threads/{self.thread.id}/close/",
            data=json.dumps({"close_reason": "request_satisfied"}),
            content_type="application/json",
        )
        self.assertEqual(close_resp.status_code, 200)
        post_resp = client.post(
            f"/api/manage/threads/{self.thread.id}/post/",
            data=json.dumps({"body": "Too late."}),
            content_type="application/json",
        )
        self.assertEqual(post_resp.status_code, 400)
        self.assertEqual(post_resp.json()["code"], "thread_closed")


class ThreadReviewFixTests(TestCase):
    """M1–M5 / L1–L6 from docs/reviews/threads-review-2026-08-24.md."""

    def setUp(self):
        self.north = create_branch("North")
        self.south = create_branch("South")
        self.opener = _make_branch_user("opener@north.dev", self.north, ROLE_OPERATOR)
        self.wh_admin = _make_warehouse_user("wh.admin@dev.com", GROUP_ADMINS)
        self.thread = create_thread(
            self.north,
            self.opener,
            "Need a 25mm brass valve",
            "Not in catalogue. Please source it.",
        )

    def _login(self, user, branch=None):
        client = Client()
        client.force_login(user)
        if branch is not None:
            session = client.session
            session[SESSION_KEY] = branch.id
            session.save()
        return client

    def test_non_string_json_returns_400(self):
        client = self._login(self.opener, self.north)
        resp = client.post(
            "/api/branch/threads/create/",
            data=json.dumps({"subject": 123, "first_message": "Need a 40mm pipe."}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 400)
        resp = client.post(
            f"/api/branch/threads/{self.thread.id}/close/",
            data=json.dumps({"close_reason": 5}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 400)
        resp = client.post(
            f"/api/branch/threads/{self.thread.id}/close/",
            data=json.dumps({"close_reason": "other", "close_reason_text": 42}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 400)
        self.thread.refresh_from_db()
        self.assertNotEqual(self.thread.status, ItemRequestThread.Status.CLOSED)

    def test_invalid_branch_id_filter_returns_400(self):
        client = self._login(self.wh_admin)
        resp = client.get("/api/manage/threads/?branch_id=abc")
        self.assertEqual(resp.status_code, 400)
        self.assertIn("integer", resp.json()["error"])

    def test_thread_list_query_count_does_not_grow_with_n(self):
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        client = self._login(self.opener, self.north)
        client.get("/api/branch/threads/")  # warm session / query cache

        def list_query_count():
            with CaptureQueriesContext(connection) as ctx:
                resp = client.get("/api/branch/threads/")
                self.assertEqual(resp.status_code, 200)
            return len(ctx)

        baseline = list_query_count()
        for i in range(6):
            create_thread(
                self.north,
                self.opener,
                f"Extra gap item {i}",
                "Still not in the catalogue.",
            )
        self.assertEqual(list_query_count(), baseline)

    def test_detail_get_does_not_mark_read(self):
        client = self._login(self.wh_admin)
        self.assertTrue(self.thread.is_unread_for(self.wh_admin))
        resp = client.get(f"/api/manage/threads/{self.thread.id}/")
        self.assertEqual(resp.status_code, 200)
        thread = ItemRequestThread.objects.get(pk=self.thread.pk)
        self.assertTrue(thread.is_unread_for(self.wh_admin))
        resp = client.post(f"/api/manage/threads/{self.thread.id}/mark-read/")
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.json()["thread"]["unread"])
        thread = ItemRequestThread.objects.get(pk=self.thread.pk)
        self.assertFalse(thread.is_unread_for(self.wh_admin))

    def test_override_close_does_not_store_satisfaction(self):
        client = self._login(self.wh_admin)
        resp = client.post(
            f"/api/manage/threads/{self.thread.id}/close/",
            data=json.dumps({
                "close_reason": "other",
                "close_reason_text": "Duplicate request.",
                "satisfaction": 5,
            }),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        self.thread.refresh_from_db()
        self.assertEqual(self.thread.status, ItemRequestThread.Status.CLOSED)
        self.assertIsNone(self.thread.satisfaction)
        self.assertIsNone(resp.json()["thread"]["satisfaction"])

    def test_link_items_api_rejects_unknown_ids(self):
        client = self._login(self.wh_admin)
        resp = client.post(
            f"/api/manage/threads/{self.thread.id}/link-items/",
            data=json.dumps({"item_ids": [999999]}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()["code"], "item_not_found")

    def test_item_search_uses_warehouse_gate(self):
        anon = Client()
        resp = anon.get("/api/manage/threads/items/search/?q=valve")
        self.assertEqual(resp.status_code, 401)
        branch_client = self._login(self.opener, self.north)
        resp = branch_client.get("/api/manage/threads/items/search/?q=valve")
        self.assertEqual(resp.status_code, 403)
        warehouse = self._login(self.wh_admin)
        resp = warehouse.get("/api/manage/threads/items/search/?q=valve")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("items", resp.json())

    def test_branch_mark_read_via_api(self):
        client = self._login(self.opener, self.north)
        post_message(self.thread, self.wh_admin, "We can source that.", ThreadMessage.Side.WAREHOUSE)
        thread = ItemRequestThread.objects.get(pk=self.thread.pk)
        self.assertTrue(thread.is_unread_for(self.opener))
        resp = client.get(f"/api/branch/threads/{self.thread.id}/")
        self.assertEqual(resp.status_code, 200)
        thread = ItemRequestThread.objects.get(pk=self.thread.pk)
        self.assertTrue(thread.is_unread_for(self.opener))
        resp = client.post(f"/api/branch/threads/{self.thread.id}/mark-read/")
        self.assertEqual(resp.status_code, 200)
        thread = ItemRequestThread.objects.get(pk=self.thread.pk)
        self.assertFalse(thread.is_unread_for(self.opener))

