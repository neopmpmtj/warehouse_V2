import json
import threading
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db import connection
from django.test import Client, TestCase, TransactionTestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from accounts.groups import (
    GROUP_ADMINS,
    GROUP_MANAGERS,
    GROUP_OPERATORS,
    assign_warehouse_group,
)
from accounts.capabilities import can_mutate_catalog
from products.models import Item, VatRate
from products.services import (
    create_family,
    create_item,
    create_supplier,
    create_supplier_item_price,
    reactivate_item,
)
from procurement import services as po_services
from procurement.models import PurchaseOrder, PurchaseOrderChangeLog
from branches.capabilities import ROLE_MANAGER, ROLE_OPERATOR
from branches.services import assign_membership, create_branch
from orders import services as order_services
from orders.models import InternalRequest

from . import services
from .models import GoodsIssue, GoodsIssueLine, GoodsReceipt, GoodsReceiptLine, StockMovement


def make_warehouse_user(email, password="test-pass-123", group_name=GROUP_ADMINS):
    user = get_user_model().objects.create_user(email=email, password=password)
    assign_warehouse_group(user, group_name)
    return user


class InventoryTestCaseMixin:
    def setUp(self):
        self.user = make_warehouse_user("inv-admin@example.com")
        self.family = create_family("Test Family")
        self.vat_rate, _ = VatRate.objects.get_or_create(
            code="VAT16",
            defaults={"label": "VAT 16%", "rate": Decimal("0.16")},
        )
        self.supplier = create_supplier(name="BuildSupply Ltd")

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

    def create_approved_po(self, quantity="10"):
        po = po_services.create_purchase_order(self.supplier, self.user)
        line = po_services.add_line(po, self.item, quantity=quantity)
        po_services.submit(po, self.user)
        po_services.approve(po, self.user)
        po.refresh_from_db()
        return po, line


class GoodsReceiptServiceTests(InventoryTestCaseMixin, TestCase):
    def test_receive_goods_writes_stock_and_movement(self):
        po, line = self.create_approved_po("10")

        receipt = services.receive_goods(
            po,
            [{"line_id": line.id, "quantity_received": "10"}],
            self.user,
            reference="GR-1",
        )

        self.item.refresh_from_db()
        po.refresh_from_db()

        self.assertEqual(self.item.quantity, Decimal("10"))
        self.assertEqual(po.status, PurchaseOrder.Status.CLOSED)
        self.assertEqual(receipt.purchase_order, po)

        movement = StockMovement.objects.get(item=self.item)
        self.assertEqual(movement.quantity, Decimal("10"))
        self.assertEqual(movement.movement_type, StockMovement.Type.RECEIPT)
        self.assertEqual(movement.content_type, ContentType.objects.get_for_model(GoodsReceipt))
        self.assertEqual(movement.object_id, receipt.id)
        self.assertEqual(movement.content_object, receipt)

        log = po.change_logs.get(action=PurchaseOrderChangeLog.Action.GOODS_RECEIVED)
        self.assertEqual(log.changes["receipt_id"], receipt.id)
        self.assertEqual(self.item.quantity, services.ledger_quantity(self.item))

    def test_partial_receipt_leaves_po_received_then_closes(self):
        po, line = self.create_approved_po("10")

        services.receive_goods(po, [{"line_id": line.id, "quantity_received": "4"}], self.user)
        self.item.refresh_from_db()
        po.refresh_from_db()
        self.assertEqual(self.item.quantity, Decimal("4"))
        self.assertEqual(po.status, PurchaseOrder.Status.RECEIVED)

        services.receive_goods(po, [{"line_id": line.id, "quantity_received": "6"}], self.user)
        self.item.refresh_from_db()
        po.refresh_from_db()
        self.assertEqual(self.item.quantity, Decimal("10"))
        self.assertEqual(po.status, PurchaseOrder.Status.CLOSED)

        self.assertEqual(
            GoodsReceiptLine.objects.filter(purchase_order_line=line).count(), 2
        )

    def test_over_receive_is_rejected(self):
        po, line = self.create_approved_po("10")
        with self.assertRaises(services.InvalidReceivedQuantityError):
            services.receive_goods(
                po, [{"line_id": line.id, "quantity_received": "11"}], self.user
            )
        self.item.refresh_from_db()
        self.assertEqual(self.item.quantity, Decimal("0"))

    def test_receive_against_non_approved_po_is_rejected(self):
        po = po_services.create_purchase_order(self.supplier, self.user)
        line = po_services.add_line(po, self.item, quantity="10")
        with self.assertRaises(services.PurchaseOrderNotReceivableError):
            services.receive_goods(
                po, [{"line_id": line.id, "quantity_received": "1"}], self.user
            )

    def test_receive_unknown_line_is_rejected(self):
        po, _line = self.create_approved_po("10")
        with self.assertRaises(services.PurchaseOrderLineNotFoundError):
            services.receive_goods(
                po, [{"line_id": 999999, "quantity_received": "1"}], self.user
            )

    def test_adjust_stock_writes_signed_movement(self):
        services.adjust_stock(self.item, "5", "found stock", self.user)
        self.item.refresh_from_db()
        self.assertEqual(self.item.quantity, Decimal("5"))

        services.adjust_stock(self.item, "-3", "correction", self.user)
        self.item.refresh_from_db()
        self.assertEqual(self.item.quantity, Decimal("2"))

        movements = StockMovement.objects.filter(item=self.item)
        self.assertEqual(movements.count(), 2)
        self.assertEqual(
            movements.filter(movement_type=StockMovement.Type.ADJUSTMENT).count(), 2
        )
        self.assertEqual(movements.first().reason, "correction")

    def test_adjust_stock_rounds_quantity_half_up(self):
        services.adjust_stock(self.item, "10.0005", "rounding", self.user)
        self.item.refresh_from_db()
        self.assertEqual(self.item.quantity, Decimal("10.001"))

    def test_adjust_stock_requires_reason(self):
        with self.assertRaises(ValidationError) as ctx:
            services.adjust_stock(self.item, "5", "   ", self.user)
        self.assertEqual(ctx.exception.code, "adjust_reason_required")

    def test_adjust_stock_zero_is_rejected(self):
        with self.assertRaises(services.InvalidAdjustmentQuantityError):
            services.adjust_stock(self.item, "0", "noop", self.user)

    def test_adjust_stock_cannot_drive_negative(self):
        services.adjust_stock(self.item, "5", "add", self.user)
        self.item.refresh_from_db()
        self.assertEqual(self.item.quantity, Decimal("5"))
        with self.assertRaises(services.NegativeStockError):
            services.adjust_stock(self.item, "-10", "over-adjust", self.user)

    def test_adjust_stock_matches_ledger_quantity(self):
        services.adjust_stock(self.item, "5", "add", self.user)
        self.item.refresh_from_db()
        self.assertEqual(self.item.quantity, services.ledger_quantity(self.item))

    def test_db_rejects_negative_item_quantity(self):
        from django.db import IntegrityError, transaction

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                self.item.quantity = Decimal("-1")
                self.item.save(update_fields=["quantity"])

    def test_adjust_stock_rejects_balance_overflow(self):
        self.item.quantity = Decimal("999999999.000")
        self.item.save(update_fields=["quantity", "updated_at"])
        with self.assertRaises(services.InvalidQuantityError):
            services.adjust_stock(self.item, "1", "overflow", self.user)

    def test_receipt_summary_reports_remaining(self):
        po, line = self.create_approved_po("10")
        services.receive_goods(po, [{"line_id": line.id, "quantity_received": "4"}], self.user)

        summary = services.get_receipt_summary(po)
        self.assertEqual(len(summary), 1)
        self.assertEqual(summary[0]["quantity"], "10.000")
        self.assertEqual(summary[0]["received"], "4.000")
        self.assertEqual(summary[0]["remaining"], "6.000")

    def test_malformed_quantity_is_rejected(self):
        po, line = self.create_approved_po("10")
        with self.assertRaises(services.InvalidQuantityError):
            services.receive_goods(
                po, [{"line_id": line.id, "quantity_received": "abc"}], self.user
            )

    def test_non_finite_quantity_is_rejected(self):
        po, line = self.create_approved_po("10")
        for bad in ("NaN", "Infinity", "-Infinity"):
            with self.assertRaises(services.InvalidQuantityError):
                services.receive_goods(
                    po, [{"line_id": line.id, "quantity_received": bad}], self.user
                )

    def test_duplicate_line_id_is_rejected(self):
        po, line = self.create_approved_po("10")
        with self.assertRaises(services.DuplicateReceiptLineError):
            services.receive_goods(
                po,
                [
                    {"line_id": line.id, "quantity_received": "3"},
                    {"line_id": line.id, "quantity_received": "3"},
                ],
                self.user,
            )
        self.item.refresh_from_db()
        self.assertEqual(self.item.quantity, Decimal("0"))

    def test_non_dict_line_is_rejected(self):
        po, _line = self.create_approved_po("10")
        with self.assertRaises(services.InvalidReceiptLineError):
            services.receive_goods(po, ["not-a-dict"], self.user)

    def test_line_missing_quantity_is_rejected(self):
        po, line = self.create_approved_po("10")
        with self.assertRaises(services.InvalidReceiptLineError):
            services.receive_goods(po, [{"line_id": line.id}], self.user)

    def test_adjust_stock_non_finite_is_rejected(self):
        for bad in ("NaN", "Infinity"):
            with self.assertRaises(services.InvalidQuantityError):
                services.adjust_stock(self.item, bad, "x", self.user)

    def test_over_precise_quantity_is_rejected(self):
        po, line = self.create_approved_po("10")
        with self.assertRaises(services.InvalidQuantityError):
            services.receive_goods(
                po, [{"line_id": line.id, "quantity_received": "0.0001"}], self.user
            )

    def test_oversized_quantity_is_rejected(self):
        po, line = self.create_approved_po("10")
        with self.assertRaises(services.InvalidQuantityError):
            services.receive_goods(
                po, [{"line_id": line.id, "quantity_received": "1000000000000"}], self.user
            )

    def test_receive_goods_locks_rows_for_update(self):
        po, line = self.create_approved_po("10")
        with CaptureQueriesContext(connection) as ctx:
            services.receive_goods(
                po, [{"line_id": line.id, "quantity_received": "2"}], self.user
            )
        for_update = [
            query["sql"]
            for query in ctx.captured_queries
            if "FOR UPDATE" in query["sql"]
        ]
        self.assertGreaterEqual(len(for_update), 1)

    def test_receive_goods_locks_items_in_pk_order(self):
        other = create_item(
            self.user,
            family=self.family,
            description="Sand 1kg",
            internal_code="SAND-1",
            unit_of_measure=Item.UnitOfMeasure.KG,
            vat_rate=self.vat_rate,
        )
        other = reactivate_item(self.user, other, reason="Genesis")
        create_supplier_item_price(
            self.supplier, other, "0.90", primary=True, user=self.user
        )
        po = po_services.create_purchase_order(self.supplier, self.user)
        line_a = po_services.add_line(po, self.item, quantity="3")
        line_b = po_services.add_line(po, other, quantity="2")
        po_services.submit(po, self.user)
        po_services.approve(po, self.user)

        with CaptureQueriesContext(connection) as ctx:
            services.receive_goods(
                po,
                [
                    {"line_id": line_a.id, "quantity_received": "3"},
                    {"line_id": line_b.id, "quantity_received": "2"},
                ],
                self.user,
            )

        item_locks = [
            query["sql"]
            for query in ctx.captured_queries
            if "FOR UPDATE" in query["sql"]
            and "products_item" in query["sql"].lower()
            and "ORDER BY" in query["sql"]
        ]
        self.assertGreaterEqual(len(item_locks), 1)

        self.item.refresh_from_db()
        other.refresh_from_db()
        self.assertEqual(self.item.quantity, Decimal("3"))
        self.assertEqual(other.quantity, Decimal("2"))
        self.assertEqual(self.item.quantity, services.ledger_quantity(self.item))
        self.assertEqual(other.quantity, services.ledger_quantity(other))


class InventoryConsoleTests(InventoryTestCaseMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.client = Client()
        self.host = {"HTTP_HOST": "localhost"}

    def _create_approved_po_via_api(self):
        po_resp = self.client.post(
            reverse("manage_purchase_order_list"),
            data=json.dumps({"supplier_id": self.supplier.id}),
            content_type="application/json",
            **self.host,
        )
        po = po_resp.json()["purchase_order"]
        self.client.post(
            reverse("manage_purchase_order_lines", args=[po["id"]]),
            data=json.dumps({"item_id": self.item.id, "quantity": "10"}),
            content_type="application/json",
            **self.host,
        )
        self.client.post(reverse("manage_purchase_order_submit", args=[po["id"]]), **self.host)
        self.client.post(reverse("manage_purchase_order_approve", args=[po["id"]]), **self.host)
        return po

    def test_admin_receives_goods_via_api(self):
        self.client.force_login(self.user)
        po = self._create_approved_po_via_api()

        summary = self.client.get(
            reverse("manage_receipt_summary", args=[po["id"]]), **self.host
        )
        self.assertEqual(summary.status_code, 200)
        line = summary.json()["lines"][0]
        self.assertEqual(line["remaining"], "10.000")

        resp = self.client.post(
            reverse("manage_goods_receipt_list"),
            data=json.dumps(
                {
                    "purchase_order_id": po["id"],
                    "reference": "DN-001",
                    "lines": [{"line_id": line["line_id"], "quantity_received": "6"}],
                }
            ),
            content_type="application/json",
            **self.host,
        )
        self.assertEqual(resp.status_code, 200)
        receipt = resp.json()["goods_receipt"]
        self.assertEqual(receipt["total_received"], "6.000")

        self.item.refresh_from_db()
        self.assertEqual(self.item.quantity, Decimal("6"))

    def test_operator_cannot_receive(self):
        operator = make_warehouse_user("inv-op@example.com", group_name=GROUP_OPERATORS)
        self.client.force_login(self.user)
        po = self._create_approved_po_via_api()

        self.client.force_login(operator)
        resp = self.client.post(
            reverse("manage_goods_receipt_list"),
            data=json.dumps(
                {
                    "purchase_order_id": po["id"],
                    "lines": [{"line_id": 1, "quantity_received": "1"}],
                }
            ),
            content_type="application/json",
            **self.host,
        )
        self.assertEqual(resp.status_code, 403)

    def test_manager_can_receive_but_not_adjust(self):
        manager = make_warehouse_user("inv-mgr@example.com", group_name=GROUP_MANAGERS)
        self.client.force_login(self.user)
        po = self._create_approved_po_via_api()

        self.client.force_login(manager)
        summary = self.client.get(
            reverse("manage_receipt_summary", args=[po["id"]]), **self.host
        )
        line = summary.json()["lines"][0]
        resp = self.client.post(
            reverse("manage_goods_receipt_list"),
            data=json.dumps(
                {
                    "purchase_order_id": po["id"],
                    "lines": [{"line_id": line["line_id"], "quantity_received": "1"}],
                }
            ),
            content_type="application/json",
            **self.host,
        )
        self.assertEqual(resp.status_code, 200)

        adjust = self.client.post(
            reverse("manage_stock_adjustment"),
            data=json.dumps({"item_id": self.item.id, "quantity": "5", "reason": "x"}),
            content_type="application/json",
            **self.host,
        )
        self.assertEqual(adjust.status_code, 403)

    def test_admin_can_adjust_stock(self):
        self.client.force_login(self.user)
        resp = self.client.post(
            reverse("manage_stock_adjustment"),
            data=json.dumps({"item_id": self.item.id, "quantity": "5", "reason": "x"}),
            content_type="application/json",
            **self.host,
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["quantity"], "5.000")
        self.assertEqual(resp.json()["balance"], "5.000")

        resp2 = self.client.post(
            reverse("manage_stock_adjustment"),
            data=json.dumps({"item_id": self.item.id, "quantity": "-2", "reason": "y"}),
            content_type="application/json",
            **self.host,
        )
        self.assertEqual(resp2.status_code, 200)
        self.assertEqual(resp2.json()["quantity"], "-2.000")
        self.assertEqual(resp2.json()["balance"], "3.000")

    def test_stock_movements_endpoint(self):
        self.client.force_login(self.user)
        po, line = self.create_approved_po("10")
        services.receive_goods(po, [{"line_id": line.id, "quantity_received": "3"}], self.user)

        resp = self.client.get(reverse("manage_stock_movements"), **self.host)
        self.assertEqual(resp.status_code, 200)
        movements = resp.json()["stock_movements"]
        self.assertEqual(len(movements), 1)
        self.assertEqual(movements[0]["quantity"], "3.000")
        self.assertEqual(movements[0]["movement_type"], "receipt")
        self.assertTrue(movements[0]["reference"].startswith("GR #"))

    def test_stock_movements_rejects_bad_item_id(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("manage_stock_movements") + "?item_id=abc")
        self.assertEqual(response.status_code, 400)

    def test_goods_receipts_pagination(self):
        self.client.force_login(self.user)
        for _ in range(2):
            po, line = self.create_approved_po("10")
            services.receive_goods(po, [{"line_id": line.id, "quantity_received": "1"}], self.user)

        resp = self.client.get(
            reverse("manage_goods_receipt_list") + "?page=1&page_size=1", **self.host
        )
        payload = resp.json()
        self.assertEqual(len(payload["goods_receipts"]), 1)
        self.assertEqual(payload["total"], 2)
        self.assertEqual(payload["num_pages"], 2)

    def test_stock_movements_pagination(self):
        self.client.force_login(self.user)
        for _ in range(2):
            po, line = self.create_approved_po("10")
            services.receive_goods(po, [{"line_id": line.id, "quantity_received": "1"}], self.user)

        resp = self.client.get(
            reverse("manage_stock_movements") + "?page=1&page_size=1", **self.host
        )
        payload = resp.json()
        self.assertEqual(len(payload["stock_movements"]), 1)
        self.assertEqual(payload["total"], 2)
        self.assertEqual(payload["num_pages"], 2)

    def test_stock_adjustment_rejects_bool_item_id(self):
        self.client.force_login(self.user)
        resp = self.client.post(
            reverse("manage_stock_adjustment"),
            data=json.dumps({"item_id": True, "quantity": "-5", "reason": "x"}),
            content_type="application/json",
            **self.host,
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn("integer", resp.json()["error"].lower())

    def test_stock_adjustment_rejects_float_item_id(self):
        self.client.force_login(self.user)
        resp = self.client.post(
            reverse("manage_stock_adjustment"),
            data=json.dumps({"item_id": 1.9, "quantity": "1", "reason": "x"}),
            content_type="application/json",
            **self.host,
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn("integer", resp.json()["error"].lower())

    def test_receipt_rejects_bool_purchase_order_id(self):
        self.client.force_login(self.user)
        resp = self.client.post(
            reverse("manage_goods_receipt_list"),
            data=json.dumps(
                {
                    "purchase_order_id": True,
                    "lines": [{"line_id": 1, "quantity_received": "1"}],
                }
            ),
            content_type="application/json",
            **self.host,
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn("integer", resp.json()["error"].lower())

    def test_malformed_receipt_returns_400(self):
        self.client.force_login(self.user)
        po = self._create_approved_po_via_api()
        resp = self.client.post(
            reverse("manage_goods_receipt_list"),
            data=json.dumps(
                {
                    "purchase_order_id": po["id"],
                    "lines": [{"line_id": 1, "quantity_received": "abc"}],
                }
            ),
            content_type="application/json",
            **self.host,
        )
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()["code"], "invalid_quantity")

    def test_group_permissions_granted(self):
        admin = make_warehouse_user("perm-adm@example.com", group_name=GROUP_ADMINS)
        manager = make_warehouse_user("perm-mgr@example.com", group_name=GROUP_MANAGERS)
        operator = make_warehouse_user("perm-op@example.com", group_name=GROUP_OPERATORS)

        self.assertTrue(admin.has_perm("inventory.add_goodsreceipt"))
        self.assertTrue(admin.has_perm("inventory.can_adjust_stock"))
        self.assertTrue(manager.has_perm("inventory.add_goodsreceipt"))
        self.assertFalse(manager.has_perm("inventory.can_adjust_stock"))
        self.assertTrue(operator.has_perm("inventory.add_goodsreceipt"))
        self.assertTrue(operator.has_perm("inventory.view_goodsreceipt"))
        self.assertFalse(can_mutate_catalog(operator))


class ConcurrentReceiptTests(InventoryTestCaseMixin, TransactionTestCase):
    """A true two-thread race test: concurrent receipts must not over-receive."""

    def test_concurrent_receipts_cannot_over_receive(self):
        po, line = self.create_approved_po("10")
        outcomes = []

        def worker(qty):
            try:
                services.receive_goods(
                    po.id,
                    [{"line_id": line.id, "quantity_received": qty}],
                    self.user,
                )
                outcomes.append("ok")
            except ValidationError:
                outcomes.append("rejected")
            finally:
                connection.close()

        threads = [threading.Thread(target=worker, args=("6",)) for _ in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        self.item.refresh_from_db()
        self.assertEqual(self.item.quantity, Decimal("6.000"))
        self.assertEqual(outcomes.count("ok"), 1)
        self.assertEqual(outcomes.count("rejected"), 1)


def _make_issue_item(description, wholesale="5.00", quantity="0"):
    family = create_family(description + " Fam")
    vat, _ = VatRate.objects.get_or_create(
        code="VAT16",
        defaults={"label": "VAT 16%", "rate": Decimal("0.16")},
    )
    return Item.objects.create(
        family=family,
        vat_rate=vat,
        description=description,
        internal_code="",
        unit_of_measure=Item.UnitOfMeasure.PIECE,
        is_active=True,
        retail_price=Decimal("10.00"),
        wholesale_price=Decimal(wholesale),
        special_price=Decimal("8.00"),
        quantity=Decimal(quantity),
        reorder_level=Decimal("0"),
    )


def _make_branch_user(email, branch, role):
    user = get_user_model().objects.create_user(email=email, password="test-pass-123")
    assign_membership(user, branch, role)
    return user


class GoodsIssueTests(TestCase):
    def setUp(self):
        self.branch = create_branch("North")
        self.operator = _make_branch_user("gi-op@example.com", self.branch, ROLE_OPERATOR)
        self.manager = _make_branch_user("gi-mgr@example.com", self.branch, ROLE_MANAGER)
        self.admin = make_warehouse_user("gi-admin@example.com")
        self.item = _make_issue_item("Widget", wholesale="5.00", quantity="10")

    def _approved_request(self, qty="10"):
        req = order_services.create_internal_request(self.branch, self.operator)
        line = order_services.add_line(req, self.item, qty, self.operator)
        req = order_services.submit(req, self.operator)
        req = order_services.approve(req, self.manager)
        req.refresh_from_db()
        return req, line

    def test_issue_decrements_stock_and_marks_shipped(self):
        req, line = self._approved_request("4")
        services.issue_goods(req, [{"line_id": line.id, "quantity_issued": "4"}], self.admin)

        self.item.refresh_from_db()
        self.assertEqual(self.item.quantity, Decimal("6.000"))
        req.refresh_from_db()
        self.assertEqual(req.status, InternalRequest.Status.SHIPPED)
        self.assertTrue(
            StockMovement.objects.filter(
                item=self.item,
                movement_type=StockMovement.Type.GOODS_ISSUE,
                quantity=Decimal("-4.000"),
            ).exists()
        )

    def test_partial_issue_marks_fulfilling(self):
        req, line = self._approved_request("10")
        services.issue_goods(req, [{"line_id": line.id, "quantity_issued": "4"}], self.admin)

        req.refresh_from_db()
        self.assertEqual(req.status, InternalRequest.Status.FULFILLING)
        self.item.refresh_from_db()
        self.assertEqual(self.item.quantity, Decimal("6.000"))

    def test_cannot_issue_more_than_remaining(self):
        req, line = self._approved_request("4")
        with self.assertRaises(services.InvalidIssuedQuantityError):
            services.issue_goods(req, [{"line_id": line.id, "quantity_issued": "5"}], self.admin)

    def test_cannot_issue_more_than_on_hand(self):
        req, line = self._approved_request("10")
        self.item.quantity = Decimal("3")
        self.item.save(update_fields=["quantity"])
        with self.assertRaises(services.InsufficientStockError):
            services.issue_goods(req, [{"line_id": line.id, "quantity_issued": "4"}], self.admin)

    def test_short_close_requires_reason_and_marks_shipped(self):
        req, line = self._approved_request("10")
        with self.assertRaises(ValidationError):
            services.short_close_issue(req, self.admin, reason="")
        req = services.short_close_issue(req, self.admin, reason="short shipment")
        req.refresh_from_db()
        self.assertEqual(req.status, InternalRequest.Status.SHIPPED)


class ConcurrentIssueTests(TransactionTestCase):
    def test_concurrent_issue_cannot_oversell_last_unit(self):
        branch = create_branch("North")
        operator = _make_branch_user("conc-op@example.com", branch, ROLE_OPERATOR)
        manager = _make_branch_user("conc-mgr@example.com", branch, ROLE_MANAGER)
        admin = make_warehouse_user("conc-admin@example.com")
        item = _make_issue_item("Widget", wholesale="5.00", quantity="1")

        req = order_services.create_internal_request(branch, operator)
        line = order_services.add_line(req, item, "1", operator)
        req = order_services.submit(req, operator)
        req = order_services.approve(req, manager)
        req.refresh_from_db()

        outcomes = []

        def worker():
            try:
                services.issue_goods(req.id, [{"line_id": line.id, "quantity_issued": "1"}], admin)
                outcomes.append("ok")
            except ValidationError:
                outcomes.append("rejected")
            finally:
                connection.close()

        threads = [threading.Thread(target=worker) for _ in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        item.refresh_from_db()
        self.assertEqual(item.quantity, Decimal("0.000"))
        self.assertEqual(outcomes.count("ok"), 1)
        self.assertEqual(outcomes.count("rejected"), 1)
