import json
import uuid
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import Client, TestCase
from django.urls import reverse

from accounts.groups import (
    GROUP_ADMINS,
    GROUP_MANAGERS,
    GROUP_OPERATORS,
    assign_warehouse_group,
    set_warehouse_grade,
)
from branches.capabilities import ROLE_ADMIN, ROLE_MANAGER, ROLE_OPERATOR
from branches.models import Branch
from branches.services import SESSION_KEY, assign_membership, create_branch
from inventory import services as inventory_services
from products.models import FamilyProduct, Item, VatRate

from .models import InternalRequest
from .services import (
    ApprovalDeniedError,
    DuplicateRequestLineError,
    InactiveBranchError,
    InactiveItemError,
    InvalidStatusTransitionError,
    RequestHasGoodsIssueError,
    SelfApprovalLimitError,
    WholesalePriceMissingError,
    add_line,
    approve,
    cancel,
    create_internal_request,
    reject,
    submit,
)


def _make_user(email):
    return get_user_model().objects.create_user(email=email, password="test-pass-123")


def _make_branch_user(email, branch, role):
    user = _make_user(email)
    assign_membership(user, branch, role)
    return user


def _make_item(description, wholesale="5.00", code="", active=True):
    family = FamilyProduct.objects.create(name="Fam " + description, is_active=True)
    vat = VatRate.objects.get(code="VAT16")
    return Item.objects.create(
        family=family,
        vat_rate=vat,
        description=description,
        internal_code=code,
        unit_of_measure=Item.UnitOfMeasure.PIECE,
        is_active=active,
        retail_price=Decimal("10.00"),
        wholesale_price=Decimal(wholesale),
        special_price=Decimal("8.00"),
        quantity=Decimal("0"),
        reorder_level=Decimal("0"),
    )


class InternalRequestWorkflowTests(TestCase):
    def setUp(self):
        self.branch = create_branch("North")
        self.operator = _make_branch_user("op@example.com", self.branch, ROLE_OPERATOR)
        self.manager = _make_branch_user("mgr@example.com", self.branch, ROLE_MANAGER)
        self.admin = _make_branch_user("adm@example.com", self.branch, ROLE_ADMIN)
        self.item = _make_item("Widget", wholesale="5.00", code="W1")

    def test_full_workflow_freezes_totals(self):
        req = create_internal_request(self.branch, self.operator)
        line = add_line(req, self.item, 10, self.operator)
        req = submit(req, self.operator)
        self.assertEqual(req.status, InternalRequest.Status.SUBMITTED)

        req = approve(req, self.admin)
        self.assertEqual(req.status, InternalRequest.Status.APPROVED)
        self.assertIsNotNone(req.approved_gross)
        self.assertEqual(req.approved_net, Decimal("50.00"))
        self.assertEqual(req.approved_gross, req.approved_net + req.approved_vat)

        line.refresh_from_db()
        self.assertEqual(line.unit_price, Decimal("5.00"))

    def test_submit_requires_lines(self):
        req = create_internal_request(self.branch, self.operator)
        with self.assertRaises(ValidationError):
            submit(req, self.operator)

    def test_duplicate_line_rejected(self):
        req = create_internal_request(self.branch, self.operator)
        add_line(req, self.item, 1, self.operator)
        with self.assertRaises(DuplicateRequestLineError):
            add_line(req, self.item, 2, self.operator)

    def test_zero_wholesale_rejected(self):
        free = _make_item("Free", wholesale="0.00", code="F1")
        req = create_internal_request(self.branch, self.operator)
        with self.assertRaises(WholesalePriceMissingError):
            add_line(req, free, 1, self.operator)

    def test_inactive_item_rejected(self):
        off = _make_item("Off", wholesale="5.00", code="OFF", active=False)
        req = create_internal_request(self.branch, self.operator)
        with self.assertRaises(InactiveItemError):
            add_line(req, off, 1, self.operator)

    def test_inactive_branch_blocks_create(self):
        self.branch.is_active = False
        self.branch.save(update_fields=["is_active"])
        with self.assertRaises(InactiveBranchError):
            create_internal_request(self.branch, self.operator)

    def test_operator_cannot_approve(self):
        req = create_internal_request(self.branch, self.operator)
        add_line(req, self.item, 1, self.operator)
        req = submit(req, self.operator)
        with self.assertRaises(ApprovalDeniedError):
            approve(req, self.operator)

    def test_manager_self_approval_cap(self):
        req = create_internal_request(self.branch, self.manager)
        add_line(req, self.item, 20, self.manager)  # gross 116 > 100 self cap
        req = submit(req, self.manager)
        with self.assertRaises(SelfApprovalLimitError):
            approve(req, self.manager)

    def test_admin_approves_unlimited(self):
        req = create_internal_request(self.branch, self.operator)
        add_line(req, self.item, 20, self.operator)
        req = submit(req, self.operator)
        req = approve(req, self.admin)
        self.assertEqual(req.status, InternalRequest.Status.APPROVED)

    def test_manager_approves_others_within_cap(self):
        req = create_internal_request(self.branch, self.operator)
        add_line(req, self.item, 1, self.operator)
        req = submit(req, self.operator)
        req = approve(req, self.manager)
        self.assertEqual(req.status, InternalRequest.Status.APPROVED)

    def test_reject_requires_reason(self):
        req = create_internal_request(self.branch, self.operator)
        add_line(req, self.item, 1, self.operator)
        req = submit(req, self.operator)
        with self.assertRaises(ValidationError):
            reject(req, self.manager, reason="")
        req = reject(req, self.manager, reason="too many")
        self.assertEqual(req.status, InternalRequest.Status.REJECTED)

    def test_cancel_draft_no_reason(self):
        req = create_internal_request(self.branch, self.operator)
        req = cancel(req, self.operator)
        self.assertEqual(req.status, InternalRequest.Status.CANCELLED)

    def test_cancel_approved_requires_manager_and_reason(self):
        req = create_internal_request(self.branch, self.operator)
        add_line(req, self.item, 1, self.operator)
        req = submit(req, self.operator)
        req = approve(req, self.admin)

        with self.assertRaises(ApprovalDeniedError):
            cancel(req, self.operator)
        with self.assertRaises(ValidationError):
            cancel(req, self.manager, reason="")
        req = cancel(req, self.manager, reason="changed mind")
        self.assertEqual(req.status, InternalRequest.Status.CANCELLED)


class InternalRequestQuerySetTests(TestCase):
    def test_for_branch_and_for_user_branches(self):
        north = create_branch("North")
        south = create_branch("South")
        user = _make_branch_user("dual@example.com", north, ROLE_OPERATOR)
        assign_membership(user, south, ROLE_OPERATOR)

        r_north = create_internal_request(north, user)
        r_south = create_internal_request(south, user)

        self.assertEqual(
            set(InternalRequest.objects.for_branch(north).values_list("id", flat=True)),
            {r_north.id},
        )
        self.assertEqual(
            set(InternalRequest.objects.for_user_branches(user).values_list("id", flat=True)),
            {r_north.id, r_south.id},
        )


class InternalRequestApiTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.branch = create_branch("North")
        self.other_branch = create_branch("South")
        self.operator = _make_branch_user("api-op@example.com", self.branch, ROLE_OPERATOR)
        self.manager = _make_branch_user("api-mgr@example.com", self.branch, ROLE_MANAGER)
        self.item = _make_item("Widget", wholesale="5.00", code="W1")

    def _login(self, user, branch=None):
        self.client.force_login(user)
        b = branch or self.branch
        session = self.client.session
        session[SESSION_KEY] = b.id
        session.save()

    def _post_json(self, url, payload):
        return self.client.post(url, data=json.dumps(payload), content_type="application/json")

    def _create_and_submit(self):
        self._login(self.operator)
        r = self._post_json(reverse("request_create"), {})
        req_id = r.json()["request"]["id"]
        self._post_json(reverse("request_add_line", args=[req_id]), {"item_id": self.item.id, "quantity": "2"})
        self._post_json(reverse("request_submit", args=[req_id]), {})
        return req_id

    def test_operator_cannot_approve(self):
        req_id = self._create_and_submit()
        r = self._post_json(reverse("request_approve", args=[req_id]), {})
        self.assertEqual(r.status_code, 403)

    def test_manager_can_approve(self):
        req_id = self._create_and_submit()
        self._login(self.manager)
        r = self._post_json(reverse("request_approve", args=[req_id]), {})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["request"]["status"], "approved")

    def test_warehouse_user_forbidden(self):
        wuser = _make_user("wh@example.com")
        assign_warehouse_group(wuser, GROUP_ADMINS)
        self.client.force_login(wuser)
        r = self.client.get(reverse("request_list"))
        self.assertEqual(r.status_code, 403)

    def test_request_page_renders(self):
        self._login(self.operator)
        r = self.client.get(reverse("request_console"))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Requisição interna")
        self.assertContains(r, 'id="settings-toggle"')
        self.assertContains(r, 'data-i18n="navBranchCatalog"')
        self.assertContains(r, "branch_requests.js")
        self.assertContains(r, "register_sw.js")
        self.assertNotContains(r, 'id="language-select"')
        self.assertNotContains(r, 'id="theme-toggle"')

    def test_other_branch_request_is_404(self):
        req_id = self._create_and_submit()
        south_user = _make_branch_user("south@example.com", self.other_branch, ROLE_OPERATOR)
        self._login(south_user, self.other_branch)
        r = self.client.get(reverse("request_detail", args=[req_id]))
        self.assertEqual(r.status_code, 404)

    def test_duplicate_line_returns_400(self):
        self._login(self.operator)
        req_id = self._post_json(reverse("request_create"), {}).json()["request"]["id"]
        self._post_json(reverse("request_add_line", args=[req_id]), {"item_id": self.item.id, "quantity": "1"})
        r = self._post_json(reverse("request_add_line", args=[req_id]), {"item_id": self.item.id, "quantity": "1"})
        self.assertEqual(r.status_code, 400)
        self.assertIn("already has a line", r.json()["error"])
        self.assertNotIn("[", r.json()["error"])


class OfflineSyncTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.branch = create_branch("North")
        self.operator = _make_branch_user("sync-op@example.com", self.branch, ROLE_OPERATOR)
        self.item = _make_item("Widget", wholesale="5.00", code="W1")
        self.client_uuid = str(uuid.uuid4())

    def _login(self):
        self.client.force_login(self.operator)
        session = self.client.session
        session[SESSION_KEY] = self.branch.id
        session.save()

    def _post_json(self, url, payload):
        return self.client.post(url, data=json.dumps(payload), content_type="application/json")

    def test_sync_creates_draft_request(self):
        self._login()
        r = self._post_json(
            reverse("request_sync"),
            {
                "client_uuid": self.client_uuid,
                "notes": "offline draft",
                "lines": [{"item_id": self.item.id, "quantity": "2"}],
            },
        )
        self.assertEqual(r.status_code, 201)
        body = r.json()
        self.assertFalse(body["idempotent"])
        self.assertEqual(body["request"]["status"], "draft")
        self.assertEqual(body["request"]["client_uuid"], self.client_uuid)
        self.assertEqual(len(body["request"]["lines"]), 1)

    def test_sync_is_idempotent(self):
        self._login()
        payload = {
            "client_uuid": self.client_uuid,
            "notes": "offline draft",
            "lines": [{"item_id": self.item.id, "quantity": "2"}],
        }
        first = self._post_json(reverse("request_sync"), payload)
        second = self._post_json(reverse("request_sync"), payload)
        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 200)
        self.assertTrue(second.json()["idempotent"])
        self.assertEqual(first.json()["request"]["id"], second.json()["request"]["id"])
        self.assertEqual(InternalRequest.objects.filter(client_uuid=self.client_uuid).count(), 1)

    def test_sync_rejects_inactive_item(self):
        inactive = _make_item("Dead", wholesale="5.00", code="DEAD", active=False)
        self._login()
        r = self._post_json(
            reverse("request_sync"),
            {
                "client_uuid": str(uuid.uuid4()),
                "lines": [{"item_id": inactive.id, "quantity": "1"}],
            },
        )
        self.assertEqual(r.status_code, 400)
        self.assertIn("inactive item", r.json()["error"].lower())

    def test_sync_requires_client_uuid(self):
        self._login()
        r = self._post_json(reverse("request_sync"), {"lines": []})
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()["code"], "client_uuid_required")

    def test_sync_rejects_unknown_item(self):
        self._login()
        r = self._post_json(
            reverse("request_sync"),
            {
                "client_uuid": str(uuid.uuid4()),
                "lines": [{"item_id": 999999999, "quantity": "1"}],
            },
        )
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()["code"], "unknown_item")

    def test_sync_rejects_cross_branch_uuid(self):
        other_branch = create_branch("South")
        self._login()
        payload = {
            "client_uuid": self.client_uuid,
            "notes": "offline draft",
            "lines": [{"item_id": self.item.id, "quantity": "1"}],
        }
        first = self._post_json(reverse("request_sync"), payload)
        self.assertEqual(first.status_code, 201)

        south_user = _make_branch_user("south-sync@example.com", other_branch, ROLE_OPERATOR)
        self.client.force_login(south_user)
        session = self.client.session
        session[SESSION_KEY] = other_branch.id
        session.save()

        second = self._post_json(reverse("request_sync"), payload)
        self.assertEqual(second.status_code, 400)
        self.assertEqual(second.json()["code"], "client_uuid_branch_mismatch")
        self.assertEqual(InternalRequest.objects.filter(client_uuid=self.client_uuid).count(), 1)

    def test_sync_rejects_invalid_client_uuid(self):
        self._login()
        r = self._post_json(
            reverse("request_sync"),
            {
                "client_uuid": "not-a-uuid",
                "lines": [{"item_id": self.item.id, "quantity": "1"}],
            },
        )
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()["code"], "invalid_client_uuid")

    def test_sync_rejects_duplicate_line_in_payload(self):
        self._login()
        r = self._post_json(
            reverse("request_sync"),
            {
                "client_uuid": str(uuid.uuid4()),
                "lines": [
                    {"item_id": self.item.id, "quantity": "1"},
                    {"item_id": self.item.id, "quantity": "2"},
                ],
            },
        )
        self.assertEqual(r.status_code, 400)
        self.assertIn("already has a line", r.json()["error"].lower())


class WarehouseConsoleTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.branch = create_branch("North")
        self.operator = _make_branch_user("wh-op@example.com", self.branch, ROLE_OPERATOR)
        self.manager = _make_branch_user("wh-mgr@example.com", self.branch, ROLE_MANAGER)
        self.item = _make_item("Widget", wholesale="5.00", code="W1")
        self.item.quantity = Decimal("10")
        self.item.save(update_fields=["quantity"])

    def _approved_request(self, qty="2"):
        req = create_internal_request(self.branch, self.operator)
        line = add_line(req, self.item, qty, self.operator)
        req = submit(req, self.operator)
        req = approve(req, self.manager)
        return req, line

    def _warehouse_user(self, email, group_name, grade=None):
        user = _make_user(email)
        assign_warehouse_group(user, group_name)
        if grade is not None:
            set_warehouse_grade(user, grade)
        return user

    def test_queue_shows_approved_not_submitted(self):
        submitted_req, _line = create_internal_request(self.branch, self.operator), None
        add_line(submitted_req, self.item, "1", self.operator)
        submitted_req = submit(submitted_req, self.operator)
        approved_req, _ = self._approved_request("2")

        admin = self._warehouse_user("wh-admin@example.com", GROUP_ADMINS)
        self.client.force_login(admin)
        r = self.client.get(reverse("warehouse_request_list"))
        self.assertEqual(r.status_code, 200)
        ids = {row["id"] for row in r.json()["requests"]}
        self.assertIn(approved_req.id, ids)
        self.assertNotIn(submitted_req.id, ids)

    def test_operator_grade1_cannot_issue(self):
        req, line = self._approved_request("2")
        op = self._warehouse_user("wh-op1@example.com", GROUP_OPERATORS)  # grade 1
        self.client.force_login(op)
        r = self._post_json(
            reverse("warehouse_request_issue", args=[req.id]),
            {"lines": [{"line_id": line.id, "quantity_issued": "1"}]},
        )
        self.assertEqual(r.status_code, 403)

    def test_manager_grade2_can_issue(self):
        req, line = self._approved_request("2")
        mgr = self._warehouse_user("wh-mgr2@example.com", GROUP_MANAGERS, grade=2)
        self.client.force_login(mgr)
        r = self._post_json(
            reverse("warehouse_request_issue", args=[req.id]),
            {"lines": [{"line_id": line.id, "quantity_issued": "1"}]},
        )
        self.assertEqual(r.status_code, 201)
        self.item.refresh_from_db()
        self.assertEqual(self.item.quantity, Decimal("9.000"))

    def test_cancel_after_issue_is_blocked(self):
        req, line = self._approved_request("2")
        admin = self._warehouse_user("wh-admin2@example.com", GROUP_ADMINS)
        inventory_services.issue_goods(
            req, [{"line_id": line.id, "quantity_issued": "1"}], admin
        )
        req.refresh_from_db()
        self.assertEqual(req.status, InternalRequest.Status.FULFILLING)
        with self.assertRaises(InvalidStatusTransitionError):
            cancel(req, self.manager, reason="changed mind")

    def test_queue_page_uses_account_settings_gear(self):
        admin = self._warehouse_user("wh-queue-ui@example.com", GROUP_ADMINS)
        self.client.force_login(admin)
        r = self.client.get(reverse("internal_request_queue_console"))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'id="settings-toggle"')
        self.assertContains(r, 'id="settings-help"')
        self.assertContains(r, "eyebrow-link")
        self.assertContains(r, "CentCompras")
        self.assertContains(r, 'id="cancel-btn"')
        self.assertContains(r, "Branch caps")
        self.assertNotContains(r, 'id="language-select"')
        self.assertNotContains(r, 'id="theme-toggle"')

    def test_branch_caps_page_uses_account_settings_gear(self):
        admin = self._warehouse_user("wh-caps-ui@example.com", GROUP_ADMINS)
        self.client.force_login(admin)
        r = self.client.get(reverse("branch_approval_limit_console"))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'id="settings-toggle"')
        self.assertContains(r, 'id="settings-help"')
        self.assertContains(r, "eyebrow-link")
        self.assertContains(r, "CentCompras")
        self.assertContains(r, "Requests")
        self.assertNotContains(r, 'id="language-select"')
        self.assertNotContains(r, 'id="theme-toggle"')

    def _post_json(self, url, payload):
        return self.client.post(url, data=json.dumps(payload), content_type="application/json")
