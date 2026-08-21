import json
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import connection
from django.test import Client, TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from accounts.groups import (
    GROUP_ADMINS,
    GROUP_MANAGERS,
    GROUP_OPERATORS,
    assign_warehouse_group,
)
from products.models import Item, Supplier, VatRate
from products.services import (
    create_family,
    create_item,
    create_supplier,
    create_supplier_item_price,
    reactivate_item,
)

from . import services
from .models import PurchaseOrder, PurchaseOrderChangeLog


def make_warehouse_user(email, password="test-pass-123", group_name=GROUP_ADMINS):
    user = get_user_model().objects.create_user(email=email, password=password)
    assign_warehouse_group(user, group_name)
    return user


class PurchaseOrderTestCaseMixin:
    def setUp(self):
        self.user = make_warehouse_user("po-admin@example.com")
        self.family = create_family("Test Family")
        self.vat_rate = VatRate.objects.get(code="VAT16")
        self.supplier = create_supplier(name="BuildSupply Ltd")
        self.other_supplier = create_supplier(name="Porto Materials Co")

        item = create_item(
            self.user,
            family=self.family,
            description="Cement 50kg",
            internal_code="CEM-50",
            unit_of_measure=Item.UnitOfMeasure.KG,
            vat_rate=self.vat_rate,
        )
        self.item = reactivate_item(self.user, item, reason="Genesis")
        self.item.refresh_from_db()

        create_supplier_item_price(
            self.supplier, self.item, "12.50", primary=True, user=self.user
        )

    def create_draft_po(self, supplier=None, user=None):
        return services.create_purchase_order(
            supplier or self.supplier,
            user or self.user,
        )


class PurchaseOrderServiceTests(PurchaseOrderTestCaseMixin, TestCase):
    def test_create_purchase_order_starts_draft_and_audits(self):
        po = self.create_draft_po()

        self.assertEqual(po.status, PurchaseOrder.Status.DRAFT)
        self.assertEqual(po.created_by, self.user)
        log = po.change_logs.get(action=PurchaseOrderChangeLog.Action.CREATED)
        self.assertEqual(log.changes["supplier"]["name"], self.supplier.name)

    def test_add_line_auto_fills_cost_from_supplier_price(self):
        po = self.create_draft_po()

        line = services.add_line(po, self.item, quantity="10")

        self.assertEqual(line.unit_cost, Decimal("12.50"))
        self.assertEqual(line.description, "Cement 50kg")
        self.assertEqual(line.internal_code, "CEM-50")
        self.assertEqual(line.vat_rate, Decimal("0.1600"))

    def test_add_line_respects_explicit_cost(self):
        po = self.create_draft_po()
        line = services.add_line(po, self.item, quantity="10", unit_cost="9.99")
        self.assertEqual(line.unit_cost, Decimal("9.99"))

    def test_add_line_rejects_item_not_in_supplier_price_list(self):
        po = services.create_purchase_order(self.other_supplier, self.user)
        with self.assertRaises(services.SupplierPriceMissingError):
            services.add_line(po, self.item, quantity="1")

    def test_line_totals_apply_discounts_and_vat(self):
        po = self.create_draft_po()
        line = services.add_line(po, self.item, quantity="10")

        services.update_line(
            line,
            user=self.user,
            discount_commercial="5",
            discount_financial="0",
            rappel="0",
        )
        line.refresh_from_db()

        self.assertEqual(line.net_unit_cost, Decimal("11.875"))
        self.assertEqual(line.line_net, Decimal("118.75"))
        self.assertEqual(line.line_total, Decimal("137.75"))

    def test_negative_quantity_is_rejected(self):
        po = self.create_draft_po()
        with self.assertRaises(ValidationError):
            services.add_line(po, self.item, quantity="-1")

    def test_nan_values_are_rejected(self):
        po = self.create_draft_po()
        with self.assertRaises(ValidationError):
            services.add_line(po, self.item, quantity="NaN")
        with self.assertRaises(ValidationError):
            services.add_line(po, self.item, quantity="1", unit_cost="NaN")
        with self.assertRaises(ValidationError):
            services.add_line(po, self.item, quantity="1", discount_commercial="NaN")

    def test_discount_out_of_range_is_rejected(self):
        po = self.create_draft_po()
        line = services.add_line(po, self.item, quantity="1")
        with self.assertRaises(ValidationError):
            services.update_line(line, discount_commercial="150")

    def test_total_discount_exceeding_100_is_rejected(self):
        po = self.create_draft_po()
        with self.assertRaises(ValidationError):
            services.add_line(
                po,
                self.item,
                quantity="1",
                discount_commercial="50",
                discount_financial="50",
                rappel="10",
            )

    def test_update_line_rejects_total_discount_over_100(self):
        po = self.create_draft_po()
        line = services.add_line(po, self.item, quantity="1")
        with self.assertRaises(ValidationError):
            services.update_line(
                line,
                discount_commercial="50",
                discount_financial="50",
                rappel="10",
            )

    def test_lines_cannot_change_after_submit(self):
        po = self.create_draft_po()
        line = services.add_line(po, self.item, quantity="1")
        services.submit(po, self.user)

        with self.assertRaises(ValidationError):
            services.update_line(line, quantity="5")

    def test_submit_requires_lines(self):
        po = self.create_draft_po()
        with self.assertRaises(ValidationError):
            services.submit(po, self.user)

    def test_approve_sets_approver_and_stub(self):
        po = self.create_draft_po()
        services.add_line(po, self.item, quantity="1")
        services.submit(po, self.user)

        po = services.approve(po, self.user)

        self.assertEqual(po.status, PurchaseOrder.Status.APPROVED)
        self.assertEqual(po.approved_by, self.user)
        self.assertIsNotNone(po.approved_at)

    def test_totals_returns_net_vat_gross(self):
        po = self.create_draft_po()
        services.add_line(po, self.item, quantity="10")

        net, vat, gross = po.totals()

        self.assertEqual(net, Decimal("125.00"))
        self.assertEqual(vat, Decimal("20.00"))
        self.assertEqual(gross, Decimal("145.00"))

    def test_approve_snapshots_approved_totals(self):
        po = self.create_draft_po()
        services.add_line(po, self.item, quantity="10")
        services.submit(po, self.user)

        po = services.approve(po, self.user)

        self.assertEqual(po.approved_net, Decimal("125.00"))
        self.assertEqual(po.approved_vat, Decimal("20.00"))
        self.assertEqual(po.approved_gross, Decimal("145.00"))

        approval_log = po.change_logs.get(
            action=PurchaseOrderChangeLog.Action.STATUS_CHANGED,
            changes__has_key="approved_gross",
        )
        self.assertEqual(approval_log.changes["approved_gross"], "145.00")

    def test_rejected_po_has_no_approved_totals(self):
        po = self.create_draft_po()
        services.add_line(po, self.item, quantity="1")
        services.submit(po, self.user)

        po = services.reject(po, self.user)

        self.assertIsNone(po.approved_net)
        self.assertIsNone(po.approved_vat)
        self.assertIsNone(po.approved_gross)

    def test_invalid_status_transition_is_rejected(self):
        po = self.create_draft_po()
        services.add_line(po, self.item, quantity="1")

        with self.assertRaises(services.InvalidStatusTransitionError):
            services.approve(po, self.user)  # draft -> approved is invalid

    def test_reject_then_close_flow(self):
        po = self.create_draft_po()
        services.add_line(po, self.item, quantity="1")
        services.submit(po, self.user)
        po = services.reject(po, self.user)
        self.assertEqual(po.status, PurchaseOrder.Status.REJECTED)

    def test_reopen_rejected_returns_to_draft_and_resubmit(self):
        po = self.create_draft_po()
        services.add_line(po, self.item, quantity="1")
        services.submit(po, self.user)
        po = services.reject(po, self.user)
        self.assertEqual(po.status, PurchaseOrder.Status.REJECTED)

        po = services.reopen(po, self.user)
        self.assertEqual(po.status, PurchaseOrder.Status.DRAFT)

        po = services.submit(po, self.user)
        self.assertEqual(po.status, PurchaseOrder.Status.SUBMITTED)

    def test_reopen_non_rejected_is_invalid(self):
        po = self.create_draft_po()
        services.add_line(po, self.item, quantity="1")
        with self.assertRaises(services.InvalidStatusTransitionError):
            services.reopen(po, self.user)

    def test_remove_line_audits(self):
        po = self.create_draft_po()
        line = services.add_line(po, self.item, quantity="1")
        services.remove_line(line, self.user)

        self.assertEqual(po.lines.count(), 0)
        self.assertTrue(
            po.change_logs.filter(action=PurchaseOrderChangeLog.Action.LINE_REMOVED).exists()
        )

    def _assert_po_for_update(self, ctx):
        for_update = [
            query["sql"]
            for query in ctx.captured_queries
            if "FOR UPDATE" in query["sql"]
            and "procurement_purchaseorder" in query["sql"].lower()
        ]
        self.assertGreaterEqual(len(for_update), 1)

    def test_add_line_locks_purchase_order_for_update(self):
        po = self.create_draft_po()
        with CaptureQueriesContext(connection) as ctx:
            services.add_line(po, self.item, quantity="1")
        self._assert_po_for_update(ctx)

    def test_update_line_locks_purchase_order_for_update(self):
        po = self.create_draft_po()
        line = services.add_line(po, self.item, quantity="1")
        with CaptureQueriesContext(connection) as ctx:
            services.update_line(line, quantity="2")
        self._assert_po_for_update(ctx)

    def test_remove_line_locks_purchase_order_for_update(self):
        po = self.create_draft_po()
        line = services.add_line(po, self.item, quantity="1")
        with CaptureQueriesContext(connection) as ctx:
            services.remove_line(line, self.user)
        self._assert_po_for_update(ctx)

    def test_submit_rejects_when_supplier_price_deleted(self):
        from products.models import SupplierItemPrice, SupplierItemPriceChangeLog

        po = self.create_draft_po()
        services.add_line(po, self.item, quantity="1")
        sip = SupplierItemPrice.objects.get(supplier=self.supplier, item=self.item)
        SupplierItemPriceChangeLog.objects.filter(supplier_item_price=sip).delete()
        sip.delete()

        with self.assertRaises(services.SupplierPriceMissingError):
            services.submit(po, self.user)

    def test_approve_rejects_when_supplier_price_deleted(self):
        from products.models import SupplierItemPrice, SupplierItemPriceChangeLog

        po = self.create_draft_po()
        services.add_line(po, self.item, quantity="1")
        services.submit(po, self.user)
        sip = SupplierItemPrice.objects.get(supplier=self.supplier, item=self.item)
        SupplierItemPriceChangeLog.objects.filter(supplier_item_price=sip).delete()
        sip.delete()

        with self.assertRaises(services.SupplierPriceMissingError):
            services.approve(po, self.user)

    def test_inactive_supplier_cannot_create_po(self):
        from products.services import update_supplier

        update_supplier(self.supplier, is_active=False)
        with self.assertRaises(services.InactiveSupplierError):
            services.create_purchase_order(self.supplier, self.user)

    def test_inactive_item_cannot_add_line(self):
        from products.services import deactivate_item

        po = self.create_draft_po()
        deactivate_item(self.user, self.item, reason="Delisted")
        with self.assertRaises(services.InactiveItemError):
            services.add_line(po, self.item, quantity="1")

    def test_submit_rejects_when_item_deactivated(self):
        from products.services import deactivate_item

        po = self.create_draft_po()
        services.add_line(po, self.item, quantity="1")
        deactivate_item(self.user, self.item, reason="Delisted")
        with self.assertRaises(services.InactiveItemError):
            services.submit(po, self.user)

    def test_submit_rejects_when_supplier_deactivated(self):
        from products.services import update_supplier

        po = self.create_draft_po()
        services.add_line(po, self.item, quantity="1")
        update_supplier(self.supplier, is_active=False)
        with self.assertRaises(services.InactiveSupplierError):
            services.submit(po, self.user)

    def test_duplicate_po_line_is_rejected(self):
        po = self.create_draft_po()
        services.add_line(po, self.item, quantity="1")
        with self.assertRaises(services.DuplicatePOLineError):
            services.add_line(po, self.item, quantity="2")
        self.assertEqual(po.lines.count(), 1)

    def test_db_rejects_duplicate_po_line_item(self):
        from django.db import IntegrityError, transaction
        from procurement.models import PurchaseOrderLine

        po = self.create_draft_po()
        services.add_line(po, self.item, quantity="1")
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                PurchaseOrderLine.objects.create(
                    purchase_order=po,
                    item=self.item,
                    description=self.item.description,
                    quantity=Decimal("1"),
                    unit_cost=Decimal("1"),
                )


class PurchaseOrderPermissionTests(TestCase):
    def test_operator_is_view_only(self):
        operator = make_warehouse_user("po-op@example.com", group_name=GROUP_OPERATORS)
        self.assertTrue(operator.has_perm("procurement.view_purchaseorder"))
        self.assertFalse(operator.has_perm("procurement.add_purchaseorder"))
        self.assertFalse(operator.has_perm("procurement.change_purchaseorder"))

    def test_manager_can_add_change_but_not_approve(self):
        manager = make_warehouse_user("po-mgr@example.com", group_name=GROUP_MANAGERS)
        self.assertTrue(manager.has_perm("procurement.add_purchaseorder"))
        self.assertTrue(manager.has_perm("procurement.change_purchaseorder"))
        self.assertFalse(manager.has_perm("procurement.can_approve"))

    def test_admin_can_approve(self):
        admin = make_warehouse_user("po-adm@example.com", group_name=GROUP_ADMINS)
        self.assertTrue(admin.has_perm("procurement.can_approve"))


class PurchaseOrderConsoleTests(PurchaseOrderTestCaseMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.client = Client()
        self.host = {"HTTP_HOST": "localhost"}

    def _create_po_via_api(self, client=None):
        client = client or self.client
        response = client.post(
            reverse("manage_purchase_order_list"),
            data=json.dumps({"supplier_id": self.supplier.id}),
            content_type="application/json",
            **self.host,
        )
        self.assertEqual(response.status_code, 200)
        return response.json()["purchase_order"]

    def test_admin_can_create_and_view_po(self):
        self.client.force_login(self.user)

        po = self._create_po_via_api()
        self.assertEqual(po["status"], "draft")
        self.assertEqual(po["supplier_name"], "BuildSupply Ltd")

        detail = self.client.get(
            reverse("manage_purchase_order_detail", args=[po["id"]]),
            **self.host,
        )
        self.assertEqual(detail.status_code, 200)

    def test_add_line_and_submit_and_approve_through_api(self):
        self.client.force_login(self.user)
        po = self._create_po_via_api()

        line_resp = self.client.post(
            reverse("manage_purchase_order_lines", args=[po["id"]]),
            data=json.dumps({"item_id": self.item.id, "quantity": "10"}),
            content_type="application/json",
            **self.host,
        )
        self.assertEqual(line_resp.status_code, 200)
        line = line_resp.json()["purchase_order"]["lines"][0]
        self.assertEqual(line["unit_cost"], "12.50")

        submit = self.client.post(
            reverse("manage_purchase_order_submit", args=[po["id"]]), **self.host
        )
        self.assertEqual(submit.json()["purchase_order"]["status"], "submitted")

        approve = self.client.post(
            reverse("manage_purchase_order_approve", args=[po["id"]]), **self.host
        )
        self.assertEqual(approve.json()["purchase_order"]["status"], "approved")

    def test_approved_po_exposes_approved_totals(self):
        self.client.force_login(self.user)
        po = self._create_po_via_api()
        self.client.post(
            reverse("manage_purchase_order_lines", args=[po["id"]]),
            data=json.dumps({"item_id": self.item.id, "quantity": "10"}),
            content_type="application/json",
            **self.host,
        )
        self.client.post(reverse("manage_purchase_order_submit", args=[po["id"]]), **self.host)
        resp = self.client.post(
            reverse("manage_purchase_order_approve", args=[po["id"]]), **self.host
        )

        data = resp.json()["purchase_order"]
        self.assertEqual(data["approved_net"], "125.00")
        self.assertEqual(data["approved_vat"], "20.00")
        self.assertEqual(data["approved_gross"], "145.00")

    def test_console_rejects_line_for_supplier_without_price(self):
        self.client.force_login(self.user)
        resp = self.client.post(
            reverse("manage_purchase_order_list"),
            data=json.dumps({"supplier_id": self.other_supplier.id}),
            content_type="application/json",
            **self.host,
        )
        po = resp.json()["purchase_order"]

        line_resp = self.client.post(
            reverse("manage_purchase_order_lines", args=[po["id"]]),
            data=json.dumps({"item_id": self.item.id, "quantity": "1"}),
            content_type="application/json",
            **self.host,
        )
        self.assertEqual(line_resp.status_code, 400)
        self.assertEqual(line_resp.json()["code"], "supplier_price_missing")

    def test_manager_cannot_approve(self):
        manager = make_warehouse_user("po-mgr2@example.com", group_name=GROUP_MANAGERS)
        self.client.force_login(self.user)
        po = self._create_po_via_api()
        self.client.post(
            reverse("manage_purchase_order_lines", args=[po["id"]]),
            data=json.dumps({"item_id": self.item.id, "quantity": "1"}),
            content_type="application/json",
            **self.host,
        )
        self.client.post(reverse("manage_purchase_order_submit", args=[po["id"]]), **self.host)

        self.client.force_login(manager)
        response = self.client.post(
            reverse("manage_purchase_order_approve", args=[po["id"]]), **self.host
        )
        self.assertEqual(response.status_code, 403)

    def test_operator_cannot_create(self):
        operator = make_warehouse_user("po-op2@example.com", group_name=GROUP_OPERATORS)
        self.client.force_login(operator)

        response = self.client.post(
            reverse("manage_purchase_order_list"),
            data=json.dumps({"supplier_id": self.supplier.id}),
            content_type="application/json",
            **self.host,
        )
        self.assertEqual(response.status_code, 403)

    def test_reopen_rejected_po_through_api(self):
        self.client.force_login(self.user)
        po = self._create_po_via_api()
        self.client.post(
            reverse("manage_purchase_order_lines", args=[po["id"]]),
            data=json.dumps({"item_id": self.item.id, "quantity": "1"}),
            content_type="application/json",
            **self.host,
        )
        self.client.post(reverse("manage_purchase_order_submit", args=[po["id"]]), **self.host)
        self.client.post(reverse("manage_purchase_order_reject", args=[po["id"]]), **self.host)

        response = self.client.post(reverse("manage_purchase_order_reopen", args=[po["id"]]), **self.host)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["purchase_order"]["status"], "draft")

    def test_add_line_unknown_item_returns_404(self):
        self.client.force_login(self.user)
        po = self._create_po_via_api()
        response = self.client.post(
            reverse("manage_purchase_order_lines", args=[po["id"]]),
            data=json.dumps({"item_id": 999999, "quantity": "1"}),
            content_type="application/json",
            **self.host,
        )
        self.assertEqual(response.status_code, 404)
        self.assertIn("not found", response.json()["error"].lower())

    def test_add_line_rejects_float_item_id(self):
        self.client.force_login(self.user)
        po = self._create_po_via_api()
        response = self.client.post(
            reverse("manage_purchase_order_lines", args=[po["id"]]),
            data=json.dumps({"item_id": 1.9, "quantity": "1"}),
            content_type="application/json",
            **self.host,
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("integer", response.json()["error"].lower())
