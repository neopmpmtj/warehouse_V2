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
    set_warehouse_grade,
)
from accounts.capabilities import can_mutate_catalog
from products.models import Item, VatRate
from products.services import (
    create_family,
    create_item,
    create_supplier,
    create_supplier_item_price,
    deactivate_item,
    reactivate_item,
)
from procurement import services as po_services
from procurement.models import PurchaseOrder, PurchaseOrderChangeLog
from branches.capabilities import ROLE_ADMIN, ROLE_MANAGER, ROLE_OPERATOR
from branches.services import SESSION_KEY, assign_membership, create_branch
from orders import services as order_services
from orders.models import InternalRequest, InternalRequestLine

from . import services
from .models import (
    BranchItemStock,
    BranchReceipt,
    BranchReceiptReadState,
    BranchStockMovement,
    GoodsIssue,
    GoodsIssueLine,
    GoodsReceipt,
    GoodsReceiptLine,
    StockMovement,
)


def make_warehouse_user(email, password="test-pass-123", group_name=GROUP_ADMINS):
    user = get_user_model().objects.create_user(email=email, password=password)
    assign_warehouse_group(user, group_name)
    return user


class InventoryTestCaseMixin:
    def setUp(self):
        self.user = make_warehouse_user("inv-admin@example.com")
        self.family = create_family("Test Family")
        self.vat_rate, _ = VatRate.objects.get_or_create(
            code="VAT14",
            defaults={"label": "14%", "rate": Decimal("0.14")},
        )
        self.supplier = create_supplier(name="BuildSupply Ltd")

        item = create_item(
            self.user,
            family=self.family,
            description="Cement 50kg",
            internal_code="CEM-50",
            unit_of_measure=Item.UnitOfMeasure.KG,
            vat_rate=self.vat_rate,
            retail_price="1.00",
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

    def test_adjust_stock_rejects_fractional_quantity(self):
        with self.assertRaises(services.InvalidQuantityError) as ctx:
            services.adjust_stock(self.item, "10.0005", "rounding", self.user)
        self.assertIn("whole number", str(ctx.exception))

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
                self.item.quantity = -1
                self.item.save(update_fields=["quantity"])

    def test_adjust_stock_rejects_balance_overflow(self):
        self.item.quantity = 999999999
        self.item.save(update_fields=["quantity", "updated_at"])
        with self.assertRaises(services.InvalidQuantityError):
            services.adjust_stock(self.item, "1", "overflow", self.user)

    def test_receipt_summary_reports_remaining(self):
        po, line = self.create_approved_po("10")
        services.receive_goods(po, [{"line_id": line.id, "quantity_received": "4"}], self.user)

        summary = services.get_receipt_summary(po)
        self.assertEqual(len(summary), 1)
        self.assertEqual(summary[0]["quantity"], "10")
        self.assertEqual(summary[0]["received"], "4")
        self.assertEqual(summary[0]["remaining"], "6")

    def test_short_close_purchase_order_wrapper(self):
        po, line = self.create_approved_po("10")
        services.receive_goods(
            po, [{"line_id": line.id, "quantity_received": "4"}], self.user
        )
        po = services.short_close_purchase_order(
            po, self.user, reason="Supplier short shipped"
        )
        self.assertEqual(po.status, PurchaseOrder.Status.CLOSED)

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
            retail_price="1.00",
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

    def test_console_header_uses_settings_popover(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse("goods_receipt_console"), **self.host)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="settings-toggle"')
        self.assertContains(response, 'id="settings-popover"')
        self.assertNotContains(response, 'id="language-select"')
        self.assertNotContains(response, 'id="theme-toggle"')
        self.assertContains(response, self.user.email)
        self.assertContains(response, reverse("logout"))
        self.assertContains(response, 'id="settings-help"')
        self.assertContains(response, 'class="help-launcher"')
        self.assertContains(response, 'class="settings-signout-link"')
        self.assertRegex(
            response.content.decode(),
            r'data-i18n="signOut"[\s\S]*id="settings-help"',
        )
        self.assertRegex(
            response.content.decode(),
            r'id="settings-popover"[^>]*\bhidden\b',
        )
        self.assertContains(response, "console_escape_close.js")

    def test_receipt_summary_api_flags_short_close(self):
        self.client.force_login(self.user)
        po = self._create_approved_po_via_api()
        line = self.client.get(
            reverse("manage_receipt_summary", args=[po["id"]]),
            **self.host,
        ).json()["lines"][0]
        self.client.post(
            reverse("manage_goods_receipt_list"),
            data=json.dumps(
                {
                    "purchase_order_id": po["id"],
                    "lines": [{"line_id": line["line_id"], "quantity_received": "4"}],
                }
            ),
            content_type="application/json",
            **self.host,
        )

        resp = self.client.get(
            reverse("manage_receipt_summary", args=[po["id"]]),
            **self.host,
        )
        payload = resp.json()
        self.assertTrue(payload["has_remaining"])
        self.assertTrue(payload["has_received"])
        self.assertTrue(payload["can_short_close"])
        self.assertEqual(payload["status"], "received")

    def test_admin_receives_goods_via_api(self):
        self.client.force_login(self.user)
        po = self._create_approved_po_via_api()

        summary = self.client.get(
            reverse("manage_receipt_summary", args=[po["id"]]), **self.host
        )
        self.assertEqual(summary.status_code, 200)
        line = summary.json()["lines"][0]
        self.assertEqual(line["remaining"], "10")

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
        self.assertEqual(receipt["total_received"], "6")

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
        self.assertEqual(resp.json()["quantity"], "5")
        self.assertEqual(resp.json()["balance"], "5")

        resp2 = self.client.post(
            reverse("manage_stock_adjustment"),
            data=json.dumps({"item_id": self.item.id, "quantity": "-2", "reason": "y"}),
            content_type="application/json",
            **self.host,
        )
        self.assertEqual(resp2.status_code, 200)
        self.assertEqual(resp2.json()["quantity"], "-2")
        self.assertEqual(resp2.json()["balance"], "3")

    def test_stock_movements_endpoint(self):
        self.client.force_login(self.user)
        po, line = self.create_approved_po("10")
        services.receive_goods(po, [{"line_id": line.id, "quantity_received": "3"}], self.user)

        resp = self.client.get(reverse("manage_stock_movements"), **self.host)
        self.assertEqual(resp.status_code, 200)
        movements = resp.json()["stock_movements"]
        self.assertEqual(len(movements), 1)
        self.assertEqual(movements[0]["quantity"], "3")
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
        self.assertEqual(self.item.quantity, 6)
        self.assertEqual(outcomes.count("ok"), 1)
        self.assertEqual(outcomes.count("rejected"), 1)


def _make_issue_item(description, wholesale="5.00", quantity="0"):
    family = create_family(description + " Fam")
    vat, _ = VatRate.objects.get_or_create(
        code="VAT14",
        defaults={"label": "14%", "rate": Decimal("0.14")},
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
        self.assertEqual(self.item.quantity, 6)
        req.refresh_from_db()
        self.assertEqual(req.status, InternalRequest.Status.SHIPPED)
        self.assertTrue(
            StockMovement.objects.filter(
                item=self.item,
                movement_type=StockMovement.Type.GOODS_ISSUE,
                quantity=-4,
            ).exists()
        )

    def test_partial_issue_marks_fulfilling(self):
        req, line = self._approved_request("10")
        services.issue_goods(req, [{"line_id": line.id, "quantity_issued": "4"}], self.admin)

        req.refresh_from_db()
        self.assertEqual(req.status, InternalRequest.Status.FULFILLING)
        self.item.refresh_from_db()
        self.assertEqual(self.item.quantity, 6)

    def test_cannot_issue_more_than_remaining(self):
        req, line = self._approved_request("4")
        with self.assertRaises(services.InvalidIssuedQuantityError):
            services.issue_goods(req, [{"line_id": line.id, "quantity_issued": "5"}], self.admin)

    def test_cannot_issue_more_than_reserved(self):
        self.item.quantity = Decimal("3")
        self.item.save(update_fields=["quantity"])
        req, line = self._approved_request("10")
        line.refresh_from_db()
        self.assertEqual(line.quantity_reserved, 3)
        with self.assertRaises(services.InsufficientReservationError) as ctx:
            services.issue_goods(req, [{"line_id": line.id, "quantity_issued": "4"}], self.admin)
        self.assertEqual(ctx.exception.code, "insufficient_reservation")

    def test_short_close_from_approved_without_dispatch_closes(self):
        req, line = self._approved_request("10")
        with self.assertRaises(ValidationError):
            services.short_close_issue(req, self.admin, reason="")
        req = services.short_close_issue(req, self.admin, reason="cannot supply")
        req.refresh_from_db()
        self.assertEqual(req.status, InternalRequest.Status.CLOSED)
        self.assertFalse(GoodsIssue.objects.filter(internal_request=req).exists())

    def test_short_close_from_fulfilling_marks_shipped(self):
        req, line = self._approved_request("10")
        services.issue_goods(req, [{"line_id": line.id, "quantity_issued": "4"}], self.admin)
        req.refresh_from_db()
        self.assertEqual(req.status, InternalRequest.Status.FULFILLING)
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
        self.assertEqual(item.quantity, 0)
        self.assertEqual(outcomes.count("ok"), 1)
        self.assertEqual(outcomes.count("rejected"), 1)


class StockReservationTests(TestCase):
    def setUp(self):
        self.north = create_branch("North")
        self.south = create_branch("South")
        self.north_op = _make_branch_user("res-n-op@example.com", self.north, ROLE_OPERATOR)
        self.north_mgr = _make_branch_user("res-n-mgr@example.com", self.north, ROLE_MANAGER)
        self.south_op = _make_branch_user("res-s-op@example.com", self.south, ROLE_OPERATOR)
        self.south_mgr = _make_branch_user("res-s-mgr@example.com", self.south, ROLE_MANAGER)
        self.admin = make_warehouse_user("res-admin@example.com")
        self.item = _make_issue_item("Widget", wholesale="5.00", quantity="10")

    def _approve(self, branch, operator, manager, qty):
        req = order_services.create_internal_request(branch, operator)
        line = order_services.add_line(req, self.item, qty, operator)
        req = order_services.submit(req, operator)
        req = order_services.approve(req, manager)
        line.refresh_from_db()
        return req, line

    def test_partial_reserve_at_approve(self):
        req, line = self._approve(self.north, self.north_op, self.north_mgr, "30")
        self.assertEqual(req.status, InternalRequest.Status.APPROVED)
        self.assertEqual(line.quantity_reserved, 10)
        self.assertEqual(services.available_quantity(self.item), 0)

    def test_later_branch_cannot_take_reserved_stock(self):
        north, north_line = self._approve(self.north, self.north_op, self.north_mgr, "30")
        south, south_line = self._approve(self.south, self.south_op, self.south_mgr, "10")
        self.assertEqual(north_line.quantity_reserved, 10)
        self.assertEqual(south_line.quantity_reserved, 0)
        with self.assertRaises(services.InsufficientReservationError):
            services.issue_goods(
                south, [{"line_id": south_line.id, "quantity_issued": "10"}], self.admin
            )
        services.issue_goods(
            north, [{"line_id": north_line.id, "quantity_issued": "10"}], self.admin
        )
        self.item.refresh_from_db()
        north_line.refresh_from_db()
        self.assertEqual(self.item.quantity, 0)
        self.assertEqual(north_line.quantity_reserved, 0)
        self.assertEqual(services.available_quantity(self.item), 0)

    def test_issue_leaves_available_unchanged(self):
        req, line = self._approve(self.north, self.north_op, self.north_mgr, "10")
        self.assertEqual(services.available_quantity(self.item), 0)
        services.issue_goods(req, [{"line_id": line.id, "quantity_issued": "4"}], self.admin)
        self.item.refresh_from_db()
        line.refresh_from_db()
        self.assertEqual(self.item.quantity, 6)
        self.assertEqual(line.quantity_reserved, 6)
        self.assertEqual(services.available_quantity(self.item), 0)

    def test_adjust_up_allocates_fifo_to_older_backorder(self):
        north, north_line = self._approve(self.north, self.north_op, self.north_mgr, "30")
        south, south_line = self._approve(self.south, self.south_op, self.south_mgr, "10")
        services.issue_goods(
            north, [{"line_id": north_line.id, "quantity_issued": "10"}], self.admin
        )
        services.adjust_stock(self.item, "15", "PO receipt", self.admin)
        north_line.refresh_from_db()
        south_line.refresh_from_db()
        self.assertEqual(north_line.quantity_reserved, 15)
        self.assertEqual(south_line.quantity_reserved, 0)

    def test_cancel_approved_reallocates_to_waiting_request(self):
        north, north_line = self._approve(self.north, self.north_op, self.north_mgr, "30")
        south, south_line = self._approve(self.south, self.south_op, self.south_mgr, "5")
        order_services.cancel(north, self.north_mgr, reason="branch no longer needs it")
        north_line.refresh_from_db()
        south_line.refresh_from_db()
        self.assertEqual(north_line.quantity_reserved, 0)
        self.assertEqual(south_line.quantity_reserved, 5)
        self.assertEqual(services.available_quantity(self.item), 5)

    def test_short_close_approved_reallocates(self):
        north, north_line = self._approve(self.north, self.north_op, self.north_mgr, "30")
        south, south_line = self._approve(self.south, self.south_op, self.south_mgr, "5")
        north = services.short_close_issue(north, self.admin, reason="cannot supply")
        north_line.refresh_from_db()
        south_line.refresh_from_db()
        self.assertEqual(north.status, InternalRequest.Status.CLOSED)
        self.assertEqual(north_line.quantity_reserved, 0)
        self.assertEqual(south_line.quantity_reserved, 5)

    def test_short_close_fulfilling_releases_unissued_reserved(self):
        north, north_line = self._approve(self.north, self.north_op, self.north_mgr, "10")
        south, south_line = self._approve(self.south, self.south_op, self.south_mgr, "5")
        services.issue_goods(
            north, [{"line_id": north_line.id, "quantity_issued": "4"}], self.admin
        )
        services.short_close_issue(north, self.admin, reason="short shipment")
        self.item.refresh_from_db()
        north_line.refresh_from_db()
        south_line.refresh_from_db()
        self.assertEqual(north_line.quantity_reserved, 0)
        self.assertEqual(south_line.quantity_reserved, 5)
        self.assertEqual(services.available_quantity(self.item), 1)

    def test_adjust_below_reserved_is_rejected(self):
        self._approve(self.north, self.north_op, self.north_mgr, "10")
        with self.assertRaises(services.AdjustBelowReservedError) as ctx:
            services.adjust_stock(self.item, "-1", "count", self.admin)
        self.assertEqual(ctx.exception.code, "adjust_below_reserved")
        self.item.refresh_from_db()
        self.assertEqual(self.item.quantity, 10)

    def test_approve_with_zero_stock_still_succeeds(self):
        self.item.quantity = Decimal("0")
        self.item.save(update_fields=["quantity"])
        req, line = self._approve(self.north, self.north_op, self.north_mgr, "8")
        self.assertEqual(req.status, InternalRequest.Status.APPROVED)
        self.assertEqual(line.quantity_reserved, 0)

    def test_backfill_gives_older_request_the_units(self):
        north, north_line = self._approve(self.north, self.north_op, self.north_mgr, "30")
        south, south_line = self._approve(self.south, self.south_op, self.south_mgr, "10")
        InternalRequestLine.objects.filter(pk__in=[north_line.pk, south_line.pk]).update(
            quantity_reserved=Decimal("0")
        )
        services.backfill_reservations()
        north_line.refresh_from_db()
        south_line.refresh_from_db()
        self.assertEqual(north_line.quantity_reserved, 10)
        self.assertEqual(south_line.quantity_reserved, 0)

    def test_issue_summary_includes_reservation_fields(self):
        req, line = self._approve(self.north, self.north_op, self.north_mgr, "30")
        summary = services.get_issue_summary(req)
        self.assertEqual(len(summary), 1)
        self.assertEqual(summary[0]["reserved"], "10")
        self.assertEqual(summary[0]["backorder"], "20")
        self.assertEqual(summary[0]["available"], "0")


class ConcurrentApproveTests(TransactionTestCase):
    def test_concurrent_approve_does_not_over_reserve(self):
        north = create_branch("North Conc")
        south = create_branch("South Conc")
        north_op = _make_branch_user("cap-n-op@example.com", north, ROLE_OPERATOR)
        north_mgr = _make_branch_user("cap-n-mgr@example.com", north, ROLE_MANAGER)
        south_op = _make_branch_user("cap-s-op@example.com", south, ROLE_OPERATOR)
        south_mgr = _make_branch_user("cap-s-mgr@example.com", south, ROLE_MANAGER)
        item = _make_issue_item("Conc Widget", wholesale="5.00", quantity="10")

        def submitted(branch, operator, qty):
            req = order_services.create_internal_request(branch, operator)
            order_services.add_line(req, item, qty, operator)
            return order_services.submit(req, operator)

        north_req = submitted(north, north_op, "10")
        south_req = submitted(south, south_op, "10")
        outcomes = []

        def worker(req, manager):
            try:
                order_services.approve(req, manager)
                outcomes.append("ok")
            except ValidationError:
                outcomes.append("rejected")
            finally:
                connection.close()

        threads = [
            threading.Thread(target=worker, args=(north_req, north_mgr)),
            threading.Thread(target=worker, args=(south_req, south_mgr)),
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        self.assertEqual(outcomes.count("ok"), 2)
        reserved = sum(
            (line.quantity_reserved for line in InternalRequestLine.objects.filter(item=item)),
            Decimal("0"),
        )
        self.assertEqual(reserved, 10)
        self.assertEqual(services.available_quantity(item), 0)


class BranchReceiptTests(TestCase):
    def setUp(self):
        self.branch = create_branch("North")
        self.operator = _make_branch_user("br-op@example.com", self.branch, ROLE_OPERATOR)
        self.manager = _make_branch_user("br-mgr@example.com", self.branch, ROLE_MANAGER)
        self.admin = _make_branch_user("br-adm@example.com", self.branch, ROLE_ADMIN)
        self.wh_admin = make_warehouse_user("br-wh-admin@example.com")
        self.item = _make_issue_item("Widget", wholesale="5.00", quantity="10")

    def _shipped_issue(self, qty="4"):
        req = order_services.create_internal_request(self.branch, self.operator)
        line = order_services.add_line(req, self.item, qty, self.operator)
        req = order_services.submit(req, self.operator)
        req = order_services.approve(req, self.manager)
        req.refresh_from_db()
        goods_issue = services.issue_goods(req, [{"line_id": line.id, "quantity_issued": qty}], self.wh_admin)
        req.refresh_from_db()
        return req, goods_issue

    def test_full_loop_receive_updates_branch_stock_and_closes(self):
        req, goods_issue = self._shipped_issue("4")
        issue_line = goods_issue.lines.get()

        services.receive_at_branch(
            goods_issue,
            [{"line_id": issue_line.id, "quantity_received": "4"}],
            self.operator,
        )

        stock = BranchItemStock.objects.get(branch=self.branch, item=self.item)
        self.assertEqual(stock.quantity, 4)
        self.assertTrue(
            BranchStockMovement.objects.filter(
                branch=self.branch, item=self.item, movement_type=BranchStockMovement.Type.RECEIPT
            ).exists()
        )
        req.refresh_from_db()
        self.assertEqual(req.status, InternalRequest.Status.CLOSED)

    def test_partial_receive_without_reason_rejected(self):
        req, goods_issue = self._shipped_issue("4")
        issue_line = goods_issue.lines.get()
        with self.assertRaises(services.DiscrepancyReasonRequiredError) as ctx:
            services.receive_at_branch(
                goods_issue,
                [{"line_id": issue_line.id, "quantity_received": "2"}],
                self.operator,
            )
        self.assertEqual(ctx.exception.code, "discrepancy_reason_required")
        req.refresh_from_db()
        self.assertEqual(req.status, InternalRequest.Status.SHIPPED)
        self.assertFalse(BranchReceipt.objects.filter(goods_issue=goods_issue).exists())

    def test_discrepancy_without_reorder_settles_line_and_closes(self):
        req, goods_issue = self._shipped_issue("4")
        issue_line = goods_issue.lines.get()
        services.receive_at_branch(
            goods_issue,
            [{"line_id": issue_line.id, "quantity_received": "2"}],
            self.operator,
            reason="broken in transit",
        )
        req.refresh_from_db()
        self.assertEqual(req.status, InternalRequest.Status.CLOSED)
        issue_line.refresh_from_db()
        self.assertEqual(issue_line.quantity_issued, 4)
        receipt = BranchReceipt.objects.get(goods_issue=goods_issue)
        self.assertTrue(receipt.is_critical)
        self.assertEqual(receipt.discrepancy_reason, "broken in transit")
        receipt_line = receipt.lines.get()
        self.assertEqual(receipt_line.quantity_received, 2)
        self.assertEqual(receipt_line.quantity_written_off, 2)
        stock = BranchItemStock.objects.get(branch=self.branch, item=self.item)
        self.assertEqual(stock.quantity, 2)
        summary = services.get_branch_issue_summary(goods_issue)[0]
        self.assertEqual(summary["remaining"], "0")
        self.assertFalse(
            InternalRequest.objects.exclude(pk=req.pk)
            .filter(branch=self.branch, created_by=self.operator)
            .exists()
        )

    def test_discrepancy_with_reorder_creates_approved_follow_up(self):
        req, goods_issue = self._shipped_issue("5")
        issue_line = goods_issue.lines.get()
        receipt = services.receive_at_branch(
            goods_issue,
            [{"line_id": issue_line.id, "quantity_received": "4", "reorder": True}],
            self.operator,
            reason="one tyre missing",
        )
        req.refresh_from_db()
        self.assertEqual(req.status, InternalRequest.Status.CLOSED)
        self.assertEqual(req.lines.get().quantity, 5)
        issue_line.refresh_from_db()
        self.assertEqual(issue_line.quantity_issued, 5)
        follow_up = InternalRequest.objects.get(pk=receipt.follow_up_request_id)
        receipt.refresh_from_db()
        self.assertEqual(receipt.follow_up_request_id, follow_up.id)
        self.assertEqual(follow_up.status, InternalRequest.Status.APPROVED)
        self.assertEqual(follow_up.branch_id, self.branch.id)
        self.assertEqual(follow_up.created_by_id, self.operator.id)
        self.assertEqual(follow_up.approved_by_id, self.operator.id)
        follow_line = follow_up.lines.get()
        self.assertEqual(follow_line.item_id, self.item.id)
        self.assertEqual(follow_line.quantity, 1)

    def test_discrepancy_reorder_qty_can_be_less_than_missing(self):
        req, goods_issue = self._shipped_issue("5")
        issue_line = goods_issue.lines.get()
        receipt = services.receive_at_branch(
            goods_issue,
            [
                {
                    "line_id": issue_line.id,
                    "quantity_received": "0",
                    "reorder": True,
                    "reorder_qty": "3",
                }
            ],
            self.operator,
            reason="keep three only",
        )
        req.refresh_from_db()
        self.assertEqual(req.status, InternalRequest.Status.CLOSED)
        issue_line.refresh_from_db()
        self.assertEqual(issue_line.quantity_issued, 5)
        receipt_line = receipt.lines.get()
        self.assertEqual(receipt_line.quantity_received, 0)
        self.assertEqual(receipt_line.quantity_written_off, 5)
        follow_up = InternalRequest.objects.get(pk=receipt.follow_up_request_id)
        self.assertEqual(follow_up.status, InternalRequest.Status.APPROVED)
        self.assertEqual(follow_up.approved_by_id, self.operator.id)
        self.assertEqual(follow_up.lines.get().quantity, 3)

    def test_discrepancy_reorder_qty_rejects_zero_and_over_missing(self):
        req, goods_issue = self._shipped_issue("5")
        issue_line = goods_issue.lines.get()
        with self.assertRaises(services.InvalidReorderQuantityError) as ctx:
            services.receive_at_branch(
                goods_issue,
                [
                    {
                        "line_id": issue_line.id,
                        "quantity_received": "0",
                        "reorder": True,
                        "reorder_qty": "0",
                    }
                ],
                self.operator,
                reason="zero",
            )
        self.assertEqual(ctx.exception.code, "invalid_reorder_quantity")
        with self.assertRaises(services.InvalidReorderQuantityError):
            services.receive_at_branch(
                goods_issue,
                [
                    {
                        "line_id": issue_line.id,
                        "quantity_received": "0",
                        "reorder": True,
                        "reorder_qty": "6",
                    }
                ],
                self.operator,
                reason="too many",
            )
        req.refresh_from_db()
        self.assertEqual(req.status, InternalRequest.Status.SHIPPED)
        self.assertFalse(BranchReceipt.objects.filter(goods_issue=goods_issue).exists())

    def test_discrepancy_zero_received_writes_off_all(self):
        req, goods_issue = self._shipped_issue("4")
        issue_line = goods_issue.lines.get()
        services.receive_at_branch(
            goods_issue,
            [{"line_id": issue_line.id, "quantity_received": "0"}],
            self.operator,
            reason="nothing arrived",
        )
        req.refresh_from_db()
        self.assertEqual(req.status, InternalRequest.Status.CLOSED)
        self.assertFalse(BranchItemStock.objects.filter(branch=self.branch, item=self.item).exists())
        receipt_line = BranchReceipt.objects.get(goods_issue=goods_issue).lines.get()
        self.assertEqual(receipt_line.quantity_received, 0)
        self.assertEqual(receipt_line.quantity_written_off, 4)

    def test_discrepancy_while_fulfilling_stays_fulfilling(self):
        req, line, goods_issue = self._partial_issue()
        issue_line = goods_issue.lines.get()
        services.receive_at_branch(
            goods_issue,
            [{"line_id": issue_line.id, "quantity_received": "3", "reorder": True}],
            self.operator,
            reason="short on this dispatch",
        )
        req.refresh_from_db()
        self.assertEqual(req.status, InternalRequest.Status.FULFILLING)
        follow_up = InternalRequest.objects.exclude(pk=req.pk).get(
            branch=self.branch, created_by=self.operator
        )
        self.assertEqual(follow_up.status, InternalRequest.Status.APPROVED)
        self.assertEqual(follow_up.lines.get().quantity, 1)
        summary = services.get_branch_issue_summary(goods_issue)[0]
        self.assertEqual(summary["remaining"], "0")

    def test_over_receipt_rejected(self):
        req, goods_issue = self._shipped_issue("4")
        issue_line = goods_issue.lines.get()
        with self.assertRaises(services.BranchInsufficientShippedError):
            services.receive_at_branch(
                goods_issue,
                [{"line_id": issue_line.id, "quantity_received": "5"}],
                self.operator,
            )

    def test_short_close_requires_reason_and_closes(self):
        req, goods_issue = self._shipped_issue("4")
        with self.assertRaises(ValidationError):
            services.short_close_receipt(req, self.manager, reason="")
        req = services.short_close_receipt(req, self.manager, reason="short shipment")
        req.refresh_from_db()
        self.assertEqual(req.status, InternalRequest.Status.CLOSED)

    def test_adjust_branch_stock_admin_only(self):
        with self.assertRaises(services.BranchAdjustmentForbiddenError):
            services.adjust_branch_stock(self.branch, self.item, "1", "reason", self.manager)
        services.adjust_branch_stock(self.branch, self.item, "3", "reason", self.admin)
        stock = BranchItemStock.objects.get(branch=self.branch, item=self.item)
        self.assertEqual(stock.quantity, 3)

    def _partial_issue(self, requested="10", issued="4"):
        req = order_services.create_internal_request(self.branch, self.operator)
        line = order_services.add_line(req, self.item, requested, self.operator)
        req = order_services.submit(req, self.operator)
        req = order_services.approve(req, self.manager)
        req.refresh_from_db()
        goods_issue = services.issue_goods(
            req,
            [{"line_id": line.id, "quantity_issued": issued}],
            self.wh_admin,
        )
        req.refresh_from_db()
        return req, line, goods_issue

    def test_partial_issue_appears_on_branch_receipts(self):
        req, line, goods_issue = self._partial_issue()
        self.assertEqual(req.status, InternalRequest.Status.FULFILLING)
        listed = list(services.get_branch_goods_issues(self.branch))
        self.assertEqual([gi.id for gi in listed], [goods_issue.id])

    def test_receive_partial_issue_stays_fulfilling(self):
        req, line, goods_issue = self._partial_issue()
        issue_line = goods_issue.lines.get()
        services.receive_at_branch(
            goods_issue,
            [{"line_id": issue_line.id, "quantity_received": "4"}],
            self.operator,
        )
        req.refresh_from_db()
        self.assertEqual(req.status, InternalRequest.Status.FULFILLING)
        stock = BranchItemStock.objects.get(branch=self.branch, item=self.item)
        self.assertEqual(stock.quantity, 4)

    def test_second_issue_new_gi_then_receive_closes(self):
        req, line, first_issue = self._partial_issue()
        first_line = first_issue.lines.get()
        services.receive_at_branch(
            first_issue,
            [{"line_id": first_line.id, "quantity_received": "4"}],
            self.operator,
        )

        second_issue = services.issue_goods(
            req,
            [{"line_id": line.id, "quantity_issued": "6"}],
            self.wh_admin,
        )
        req.refresh_from_db()
        self.assertEqual(req.status, InternalRequest.Status.SHIPPED)
        self.assertNotEqual(second_issue.id, first_issue.id)
        listed_ids = {gi.id for gi in services.get_branch_goods_issues(self.branch)}
        self.assertEqual(listed_ids, {first_issue.id, second_issue.id})

        services.receive_at_branch(
            second_issue,
            [{"line_id": second_issue.lines.get().id, "quantity_received": "6"}],
            self.operator,
        )
        req.refresh_from_db()
        self.assertEqual(req.status, InternalRequest.Status.CLOSED)
        stock = BranchItemStock.objects.get(branch=self.branch, item=self.item)
        self.assertEqual(stock.quantity, 10)

    def test_short_close_receipt_while_fulfilling_rejected(self):
        req, line, goods_issue = self._partial_issue()
        with self.assertRaises(services.BranchShortCloseWarehouseOpenError) as ctx:
            services.short_close_receipt(req, self.manager, reason="cannot wait")
        self.assertEqual(ctx.exception.code, "branch_short_close_warehouse_open")
        req.refresh_from_db()
        self.assertEqual(req.status, InternalRequest.Status.FULFILLING)

    def test_warehouse_short_close_after_full_receive_closes(self):
        req, line, goods_issue = self._partial_issue()
        issue_line = goods_issue.lines.get()
        services.receive_at_branch(
            goods_issue,
            [{"line_id": issue_line.id, "quantity_received": "4"}],
            self.operator,
        )
        req = services.short_close_issue(req, self.wh_admin, reason="cannot supply rest")
        req.refresh_from_db()
        self.assertEqual(req.status, InternalRequest.Status.CLOSED)


class BranchReceiptApiTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.branch = create_branch("North")
        self.operator = _make_branch_user("api-br-op@example.com", self.branch, ROLE_OPERATOR)
        self.manager = _make_branch_user("api-br-mgr@example.com", self.branch, ROLE_MANAGER)
        self.admin = _make_branch_user("api-br-adm@example.com", self.branch, ROLE_ADMIN)
        self.wh_admin = make_warehouse_user("api-br-wh@example.com")
        self.item = _make_issue_item("Widget", wholesale="5.00", quantity="10")

    def _login(self, user):
        self.client.force_login(user)
        session = self.client.session
        session[SESSION_KEY] = self.branch.id
        session.save()

    def _post(self, url, payload):
        return self.client.post(url, data=json.dumps(payload), content_type="application/json")

    def _shipped_issue(self, qty="4"):
        req = order_services.create_internal_request(self.branch, self.operator)
        line = order_services.add_line(req, self.item, qty, self.operator)
        req = order_services.submit(req, self.operator)
        req = order_services.approve(req, self.manager)
        req.refresh_from_db()
        goods_issue = services.issue_goods(req, [{"line_id": line.id, "quantity_issued": qty}], self.wh_admin)
        req.refresh_from_db()
        return req, goods_issue

    def test_receipts_page_uses_account_settings_gear(self):
        self._login(self.operator)
        r = self.client.get(reverse("branch_receipt_console"))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'id="settings-toggle"')
        self.assertContains(r, "Catalog")
        self.assertContains(r, 'id="report-discrepancies-btn"')
        self.assertContains(r, "colReorderQty")
        self.assertContains(r, 'id="history-body"')
        self.assertContains(r, 'id="movements-body"')
        self.assertContains(r, 'id="adjust-dialog"')
        self.assertNotContains(r, 'id="adjust-row"')
        self.assertContains(r, "Requests")
        self.assertNotContains(r, 'id="language-select"')
        self.assertNotContains(r, 'id="theme-toggle"')

    def test_operator_can_receive(self):
        req, goods_issue = self._shipped_issue("4")
        issue_line = goods_issue.lines.get()
        self._login(self.operator)
        r = self._post(
            reverse("branch_receipt_receive", args=[goods_issue.id]),
            {"lines": [{"line_id": issue_line.id, "quantity_received": "4"}]},
        )
        self.assertEqual(r.status_code, 201)
        req.refresh_from_db()
        self.assertEqual(req.status, InternalRequest.Status.CLOSED)

    def test_operator_discrepancy_requires_reason(self):
        req, goods_issue = self._shipped_issue("4")
        issue_line = goods_issue.lines.get()
        self._login(self.operator)
        r = self._post(
            reverse("branch_receipt_receive", args=[goods_issue.id]),
            {"lines": [{"line_id": issue_line.id, "quantity_received": "2"}]},
        )
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()["code"], "discrepancy_reason_required")

    def test_operator_discrepancy_with_reorder_returns_follow_up(self):
        req, goods_issue = self._shipped_issue("5")
        issue_line = goods_issue.lines.get()
        self._login(self.operator)
        r = self._post(
            reverse("branch_receipt_receive", args=[goods_issue.id]),
            {
                "lines": [{"line_id": issue_line.id, "quantity_received": "4", "reorder": True}],
                "reason": "one missing",
            },
        )
        self.assertEqual(r.status_code, 201)
        self.assertIn("follow_up_request_id", r.json())
        follow_up = InternalRequest.objects.get(pk=r.json()["follow_up_request_id"])
        self.assertEqual(follow_up.status, InternalRequest.Status.APPROVED)
        self.assertEqual(follow_up.approved_by_id, self.operator.id)
        self.assertEqual(follow_up.lines.get().quantity, 1)
        req, goods_issue = self._shipped_issue("4")
        self._login(self.operator)
        r = self._post(reverse("branch_receipt_short_close", args=[goods_issue.id]), {"reason": "x"})
        self.assertEqual(r.status_code, 403)

    def test_operator_discrepancy_reorder_qty_less_than_missing(self):
        req, goods_issue = self._shipped_issue("5")
        issue_line = goods_issue.lines.get()
        self._login(self.operator)
        r = self._post(
            reverse("branch_receipt_receive", args=[goods_issue.id]),
            {
                "lines": [
                    {
                        "line_id": issue_line.id,
                        "quantity_received": "0",
                        "reorder": True,
                        "reorder_qty": 3,
                    }
                ],
                "reason": "keep three",
            },
        )
        self.assertEqual(r.status_code, 201)
        follow_up = InternalRequest.objects.get(pk=r.json()["follow_up_request_id"])
        self.assertEqual(follow_up.status, InternalRequest.Status.APPROVED)
        self.assertEqual(follow_up.lines.get().quantity, 3)
        receipt = BranchReceipt.objects.get(goods_issue=goods_issue)
        self.assertEqual(receipt.lines.get().quantity_written_off, 5)

    def test_operator_discrepancy_reorder_qty_over_missing_is_400(self):
        req, goods_issue = self._shipped_issue("5")
        issue_line = goods_issue.lines.get()
        self._login(self.operator)
        r = self._post(
            reverse("branch_receipt_receive", args=[goods_issue.id]),
            {
                "lines": [
                    {
                        "line_id": issue_line.id,
                        "quantity_received": "0",
                        "reorder": True,
                        "reorder_qty": 6,
                    }
                ],
                "reason": "too many",
            },
        )
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()["code"], "invalid_reorder_quantity")

    def test_manager_can_short_close(self):
        req, goods_issue = self._shipped_issue("4")
        self._login(self.manager)
        r = self._post(reverse("branch_receipt_short_close", args=[goods_issue.id]), {"reason": "short"})
        self.assertEqual(r.status_code, 200)
        req.refresh_from_db()
        self.assertEqual(req.status, InternalRequest.Status.CLOSED)

    def test_non_admin_cannot_adjust(self):
        self._login(self.manager)
        r = self._post(reverse("branch_stock_adjust"), {"item_id": self.item.id, "quantity": "1", "reason": "x"})
        self.assertEqual(r.status_code, 403)

    def test_admin_can_adjust(self):
        self._login(self.admin)
        r = self._post(reverse("branch_stock_adjust"), {"item_id": self.item.id, "quantity": "3", "reason": "x"})
        self.assertEqual(r.status_code, 200)
        stock = BranchItemStock.objects.get(branch=self.branch, item=self.item)
        self.assertEqual(stock.quantity, 3)

    def _partial_issue(self, requested="10", issued="4"):
        req = order_services.create_internal_request(self.branch, self.operator)
        line = order_services.add_line(req, self.item, requested, self.operator)
        req = order_services.submit(req, self.operator)
        req = order_services.approve(req, self.manager)
        req.refresh_from_db()
        goods_issue = services.issue_goods(
            req,
            [{"line_id": line.id, "quantity_issued": issued}],
            self.wh_admin,
        )
        req.refresh_from_db()
        return req, line, goods_issue

    def test_list_includes_partial_issue_while_fulfilling(self):
        req, line, goods_issue = self._partial_issue()
        self._login(self.operator)
        r = self.client.get(reverse("branch_receipt_issue_list"))
        self.assertEqual(r.status_code, 200)
        ids = [row["id"] for row in r.json()["goods_issues"]]
        self.assertIn(goods_issue.id, ids)
        row = next(item for item in r.json()["goods_issues"] if item["id"] == goods_issue.id)
        self.assertEqual(row["request_status"], InternalRequest.Status.FULFILLING)

    def test_short_close_while_fulfilling_returns_400(self):
        req, line, goods_issue = self._partial_issue()
        self._login(self.manager)
        r = self._post(
            reverse("branch_receipt_short_close", args=[goods_issue.id]),
            {"reason": "cannot wait"},
        )
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()["code"], "branch_short_close_warehouse_open")
        req.refresh_from_db()
        self.assertEqual(req.status, InternalRequest.Status.FULFILLING)

    def test_operator_can_receive_partial_issue(self):
        req, line, goods_issue = self._partial_issue()
        issue_line = goods_issue.lines.get()
        self._login(self.operator)
        r = self._post(
            reverse("branch_receipt_receive", args=[goods_issue.id]),
            {"lines": [{"line_id": issue_line.id, "quantity_received": "4"}]},
        )
        self.assertEqual(r.status_code, 201)
        req.refresh_from_db()
        self.assertEqual(req.status, InternalRequest.Status.FULFILLING)


class BranchStockVisibilityApiTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.north = create_branch("North Stock")
        self.south = create_branch("South Stock")
        self.operator = _make_branch_user("stock-op@example.com", self.north, ROLE_OPERATOR)
        self.manager = _make_branch_user("stock-mgr@example.com", self.north, ROLE_MANAGER)
        self.admin = _make_branch_user("stock-adm@example.com", self.north, ROLE_ADMIN)
        self.south_op = _make_branch_user("stock-south@example.com", self.south, ROLE_OPERATOR)
        self.wh_admin = make_warehouse_user("stock-wh@example.com")
        self.item = _make_issue_item("Stock Widget", wholesale="5.00", quantity="20")

    def _login(self, user, branch):
        self.client.force_login(user)
        session = self.client.session
        session[SESSION_KEY] = branch.id
        session.save()

    def _ship(self, qty="4", item=None):
        item = item or self.item
        req = order_services.create_internal_request(self.north, self.operator)
        line = order_services.add_line(req, item, qty, self.operator)
        req = order_services.submit(req, self.operator)
        req = order_services.approve(req, self.manager)
        req.refresh_from_db()
        goods_issue = services.issue_goods(
            req, [{"line_id": line.id, "quantity_issued": qty}], self.wh_admin
        )
        req.refresh_from_db()
        return req, goods_issue

    def _receive(self, goods_issue, qty, reason=""):
        issue_line = goods_issue.lines.get()
        payload = {"lines": [{"line_id": issue_line.id, "quantity_received": qty}]}
        if reason:
            payload["reason"] = reason
        return self.client.post(
            reverse("branch_receipt_receive", args=[goods_issue.id]),
            data=json.dumps(payload),
            content_type="application/json",
        )

    def test_operator_can_open_stock_page(self):
        self._login(self.operator, self.north)
        response = self.client.get(reverse("branch_stock_console"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="stock-body"')
        self.assertContains(response, "navBranchStock")
        self.assertContains(response, "branch_stock.js")
        self.assertContains(response, "No stock yet. Receive a dispatch to add items.")

    def test_on_hand_empty_then_received_qty(self):
        self._login(self.operator, self.north)
        empty = self.client.get(reverse("branch_stock_list"))
        self.assertEqual(empty.status_code, 200)
        self.assertEqual(empty.json()["items"], [])

        req, goods_issue = self._ship("4")
        receive = self._receive(goods_issue, "4")
        self.assertEqual(receive.status_code, 201)

        after = self.client.get(reverse("branch_stock_list"))
        items = after.json()["items"]
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["id"], self.item.id)
        self.assertEqual(items[0]["on_hand"], "4")

        history = self.client.get(reverse("branch_receipt_history_list"))
        self.assertEqual(history.status_code, 200)
        receipts = history.json()["branch_receipts"]
        self.assertEqual(len(receipts), 1)
        self.assertEqual(receipts[0]["dispatch_id"], goods_issue.id)
        self.assertEqual(receipts[0]["total_received"], "4")
        self.assertFalse(receipts[0]["is_critical"])

        movements = self.client.get(reverse("branch_stock_movement_list"))
        self.assertEqual(movements.status_code, 200)
        rows = movements.json()["stock_movements"]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["quantity"], "4")
        self.assertEqual(rows[0]["movement_type"], BranchStockMovement.Type.RECEIPT)
        self.assertEqual(rows[0]["reference"], f"BR #{receipts[0]['id']}")

    def test_discrepancy_books_actual_qty_not_shipped(self):
        req, goods_issue = self._ship("5")
        issue_line = goods_issue.lines.get()
        self._login(self.operator, self.north)
        receive = self.client.post(
            reverse("branch_receipt_receive", args=[goods_issue.id]),
            data=json.dumps(
                {
                    "lines": [{"line_id": issue_line.id, "quantity_received": "4"}],
                    "reason": "one missing",
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(receive.status_code, 201)
        stock = self.client.get(reverse("branch_stock_list"))
        row = next(item for item in stock.json()["items"] if item["id"] == self.item.id)
        self.assertEqual(row["on_hand"], "4")
        history = self.client.get(reverse("branch_receipt_history_list")).json()
        self.assertTrue(history["branch_receipts"][0]["is_critical"])

    def test_other_branch_cannot_see_receipts_or_movements(self):
        req, goods_issue = self._ship("4")
        issue_line = goods_issue.lines.get()
        self._login(self.operator, self.north)
        self.client.post(
            reverse("branch_receipt_receive", args=[goods_issue.id]),
            data=json.dumps(
                {"lines": [{"line_id": issue_line.id, "quantity_received": "4"}]}
            ),
            content_type="application/json",
        )
        self._login(self.south_op, self.south)
        history = self.client.get(reverse("branch_receipt_history_list"))
        self.assertEqual(history.json()["branch_receipts"], [])
        movements = self.client.get(reverse("branch_stock_movement_list"))
        self.assertEqual(movements.json()["stock_movements"], [])
        stock = self.client.get(reverse("branch_stock_list"))
        ids = [item["id"] for item in stock.json()["items"]]
        self.assertNotIn(self.item.id, ids)

    def test_second_receive_same_item_does_not_duplicate(self):
        self._login(self.operator, self.north)
        _, first = self._ship("4")
        self.assertEqual(self._receive(first, "4").status_code, 201)
        _, second = self._ship("3")
        self.assertEqual(self._receive(second, "3").status_code, 201)
        items = self.client.get(reverse("branch_stock_list")).json()["items"]
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["id"], self.item.id)
        self.assertEqual(items[0]["on_hand"], "7")

    def test_receive_different_item_adds_second_row(self):
        other = _make_issue_item("Other Widget", quantity="10")
        self._login(self.operator, self.north)
        _, first = self._ship("4")
        self.assertEqual(self._receive(first, "4").status_code, 201)
        _, second = self._ship("2", item=other)
        self.assertEqual(self._receive(second, "2").status_code, 201)
        items = self.client.get(reverse("branch_stock_list")).json()["items"]
        ids = {row["id"]: row["on_hand"] for row in items}
        self.assertEqual(len(ids), 2)
        self.assertEqual(ids[self.item.id], "4")
        self.assertEqual(ids[other.id], "2")

    def test_admin_adjust_unseen_item_adds_row(self):
        unseen = _make_issue_item("Unseen Widget", quantity="0")
        self._login(self.admin, self.north)
        before = self.client.get(reverse("branch_stock_list"))
        self.assertEqual(before.json()["items"], [])
        response = self.client.post(
            reverse("branch_stock_adjust"),
            data=json.dumps(
                {"item_id": unseen.id, "quantity": "2", "reason": "opening balance"}
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        items = self.client.get(reverse("branch_stock_list")).json()["items"]
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["id"], unseen.id)
        self.assertEqual(items[0]["on_hand"], "2")

    def test_deactivated_warehouse_item_stays_listed(self):
        self._login(self.operator, self.north)
        _, goods_issue = self._ship("4")
        self.assertEqual(self._receive(goods_issue, "4").status_code, 201)
        deactivate_item(self.wh_admin, self.item, reason="retired")
        items = self.client.get(reverse("branch_stock_list")).json()["items"]
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["id"], self.item.id)
        self.assertEqual(items[0]["on_hand"], "4")

    def test_history_pagination(self):
        req, goods_issue = self._ship("4")
        issue_line = goods_issue.lines.get()
        self._login(self.operator, self.north)
        self.client.post(
            reverse("branch_receipt_receive", args=[goods_issue.id]),
            data=json.dumps(
                {"lines": [{"line_id": issue_line.id, "quantity_received": "4"}]}
            ),
            content_type="application/json",
        )
        page = self.client.get(reverse("branch_receipt_history_list") + "?page=1&page_size=1")
        self.assertEqual(page.status_code, 200)
        payload = page.json()
        self.assertEqual(payload["page"], 1)
        self.assertEqual(payload["page_size"], 1)
        self.assertEqual(len(payload["branch_receipts"]), 1)
        self.assertGreaterEqual(payload["total"], 1)

    def test_manager_adjust_dialog_still_403(self):
        self._login(self.manager, self.north)
        response = self.client.post(
            reverse("branch_stock_adjust"),
            data=json.dumps({"item_id": self.item.id, "quantity": "1", "reason": "x"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 403)


class BranchConsumptionApiTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.north = create_branch("North Consume")
        self.south = create_branch("South Consume")
        self.operator = _make_branch_user("consume-op@example.com", self.north, ROLE_OPERATOR)
        self.manager = _make_branch_user("consume-mgr@example.com", self.north, ROLE_MANAGER)
        self.admin = _make_branch_user("consume-adm@example.com", self.north, ROLE_ADMIN)
        self.south_op = _make_branch_user("consume-south@example.com", self.south, ROLE_OPERATOR)
        self.wh_admin = make_warehouse_user("consume-wh@example.com")
        self.item = _make_issue_item("Consume Widget", wholesale="5.00", quantity="20")
        self.other = _make_issue_item("Unlisted Widget", wholesale="5.00", quantity="10")

    def _login(self, user, branch):
        self.client.force_login(user)
        session = self.client.session
        session[SESSION_KEY] = branch.id
        session.save()

    def _seed(self, qty="5"):
        services.adjust_branch_stock(self.north, self.item, qty, "seed", self.admin)

    def _post(self, payload):
        return self.client.post(
            reverse("branch_consumption_list"),
            data=json.dumps(payload),
            content_type="application/json",
        )

    def test_operator_can_open_page(self):
        self._login(self.operator, self.north)
        response = self.client.get(reverse("branch_consumption_console"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "branch_consumption.js")
        self.assertContains(response, "navBranchConsume")

    def test_operator_consume_drops_on_hand(self):
        self._seed("5")
        self._login(self.operator, self.north)
        response = self._post(
            {
                "reason": "used on site",
                "lines": [{"item_id": self.item.id, "quantity": "2"}],
            }
        )
        self.assertEqual(response.status_code, 201)
        payload = response.json()
        self.assertEqual(payload["line_count"], 1)
        self.assertEqual(payload["total_quantity"], "2")
        self.assertEqual(payload["reason"], "used on site")
        stock = self.client.get(reverse("branch_stock_list")).json()["items"]
        row = next(item for item in stock if item["id"] == self.item.id)
        self.assertEqual(row["on_hand"], "3")
        listed = self.client.get(reverse("branch_consumption_list")).json()["consumptions"]
        self.assertEqual(len(listed), 1)
        self.assertEqual(listed[0]["id"], payload["id"])
        movements = self.client.get(reverse("branch_stock_movement_list")).json()["stock_movements"]
        consume_rows = [
            row for row in movements if row["movement_type"] == BranchStockMovement.Type.CONSUMPTION
        ]
        self.assertEqual(len(consume_rows), 1)
        self.assertEqual(consume_rows[0]["quantity"], "-2")
        self.assertEqual(consume_rows[0]["reference"], f"BC #{payload['id']}")

    def test_manager_can_consume(self):
        self._seed("4")
        self._login(self.manager, self.north)
        response = self._post(
            {
                "reason": "counter sale",
                "lines": [{"item_id": self.item.id, "quantity": "1"}],
            }
        )
        self.assertEqual(response.status_code, 201)

    def test_exceeds_on_hand(self):
        self._seed("2")
        self._login(self.operator, self.north)
        response = self._post(
            {
                "reason": "too much",
                "lines": [{"item_id": self.item.id, "quantity": "3"}],
            }
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["code"], "branch_consume_exceeds_on_hand")
        self.assertIn("Cannot consume 3 of", response.json()["error"])

    def test_reason_required(self):
        self._seed("2")
        self._login(self.operator, self.north)
        response = self._post(
            {"reason": "  ", "lines": [{"item_id": self.item.id, "quantity": "1"}]}
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["code"], "branch_consume_reason_required")

    def test_duplicate_item(self):
        self._seed("5")
        self._login(self.operator, self.north)
        response = self._post(
            {
                "reason": "dup",
                "lines": [
                    {"item_id": self.item.id, "quantity": "1"},
                    {"item_id": self.item.id, "quantity": "1"},
                ],
            }
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["code"], "duplicate_branch_consume_line")

    def test_item_not_on_local_list(self):
        self._seed("5")
        self._login(self.operator, self.north)
        response = self._post(
            {
                "reason": "unknown",
                "lines": [{"item_id": self.other.id, "quantity": "1"}],
            }
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["code"], "branch_consume_item_not_in_stock")

    def test_other_branch_cannot_see_ticket(self):
        self._seed("5")
        self._login(self.operator, self.north)
        created = self._post(
            {
                "reason": "north only",
                "lines": [{"item_id": self.item.id, "quantity": "1"}],
            }
        )
        self.assertEqual(created.status_code, 201)
        ticket_id = created.json()["id"]
        self._login(self.south_op, self.south)
        listed = self.client.get(reverse("branch_consumption_list"))
        self.assertEqual(listed.json()["consumptions"], [])
        detail = self.client.get(reverse("branch_consumption_detail", args=[ticket_id]))
        self.assertEqual(detail.status_code, 404)

    def test_warehouse_user_forbidden(self):
        self.client.force_login(self.wh_admin)
        page = self.client.get(reverse("branch_consumption_console"))
        self.assertEqual(page.status_code, 403)
        api = self._post(
            {
                "reason": "no",
                "lines": [{"item_id": self.item.id, "quantity": "1"}],
            }
        )
        self.assertEqual(api.status_code, 403)

    def test_full_consume_keeps_zero_row(self):
        self._seed("3")
        self._login(self.operator, self.north)
        response = self._post(
            {
                "reason": "used all",
                "lines": [{"item_id": self.item.id, "quantity": "3"}],
            }
        )
        self.assertEqual(response.status_code, 201)
        stock = self.client.get(reverse("branch_stock_list")).json()["items"]
        row = next(item for item in stock if item["id"] == self.item.id)
        self.assertEqual(row["on_hand"], "0")


class BranchReceiptAlertTests(TestCase):
    def setUp(self):
        self.north = create_branch("North Alerts")
        self.south = create_branch("South Alerts")
        self.operator = _make_branch_user("alert-op@example.com", self.north, ROLE_OPERATOR)
        self.manager = _make_branch_user("alert-mgr@example.com", self.north, ROLE_MANAGER)
        self.other_manager = _make_branch_user(
            "alert-mgr-south@example.com", self.south, ROLE_MANAGER
        )
        self.wh_admin = make_warehouse_user("alert-wh-admin@example.com")
        self.wh_operator = make_warehouse_user(
            "alert-wh-op@example.com", group_name=GROUP_OPERATORS
        )
        self.wh_manager_g1 = make_warehouse_user(
            "alert-wh-mgr1@example.com", group_name=GROUP_MANAGERS
        )
        self.wh_manager_g2 = make_warehouse_user(
            "alert-wh-mgr2@example.com", group_name=GROUP_MANAGERS
        )
        set_warehouse_grade(self.wh_manager_g2, 2)
        self.item = _make_issue_item("Alert Widget", wholesale="5.00", quantity="20")

    def _login_branch(self, user, branch):
        self.client.force_login(user)
        session = self.client.session
        session[SESSION_KEY] = branch.id
        session.save()

    def _critical_receipt(self, branch, operator, manager, qty="5", received="4", reorder=True):
        req = order_services.create_internal_request(branch, operator)
        line = order_services.add_line(req, self.item, qty, operator)
        req = order_services.submit(req, operator)
        req = order_services.approve(req, manager)
        req.refresh_from_db()
        goods_issue = services.issue_goods(
            req, [{"line_id": line.id, "quantity_issued": qty}], self.wh_admin
        )
        receipt = services.receive_at_branch(
            goods_issue,
            [
                {
                    "line_id": goods_issue.lines.get().id,
                    "quantity_received": received,
                    "reorder": reorder,
                }
            ],
            operator,
            reason="short count",
        )
        return req, goods_issue, receipt

    def test_warehouse_operator_and_grade1_manager_are_forbidden(self):
        self.client.force_login(self.wh_operator)
        self.assertEqual(self.client.get(reverse("warehouse_alerts_console")).status_code, 403)
        self.assertEqual(self.client.get(reverse("manage_alerts_list")).status_code, 403)
        self.client.force_login(self.wh_manager_g1)
        self.assertEqual(self.client.get(reverse("warehouse_alerts_console")).status_code, 403)
        self.assertEqual(self.client.get(reverse("manage_alerts_list")).status_code, 403)

    def test_branch_operator_is_forbidden(self):
        self._login_branch(self.operator, self.north)
        self.assertEqual(self.client.get(reverse("branch_alerts_console")).status_code, 403)
        self.assertEqual(self.client.get(reverse("branch_alerts_list")).status_code, 403)

    def test_warehouse_list_all_branches_and_follow_up_id(self):
        north_req, north_gi, north_receipt = self._critical_receipt(
            self.north, self.operator, self.manager
        )
        south_op = _make_branch_user("alert-south-op@example.com", self.south, ROLE_OPERATOR)
        south_req, south_gi, south_receipt = self._critical_receipt(
            self.south, south_op, self.other_manager, qty="3", received="1", reorder=False
        )
        self.client.force_login(self.wh_admin)
        page = self.client.get(reverse("warehouse_alerts_console"))
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, "Receipt discrepancies")
        self.assertContains(page, 'id="alerts-list"')
        response = self.client.get(reverse("manage_alerts_list"))
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        ids = [row["id"] for row in payload["alerts"]]
        self.assertIn(north_receipt.id, ids)
        self.assertIn(south_receipt.id, ids)
        self.assertEqual(payload["unread_count"], 2)
        north_row = next(row for row in payload["alerts"] if row["id"] == north_receipt.id)
        self.assertEqual(north_row["request_id"], north_req.id)
        self.assertEqual(north_row["dispatch_id"], north_gi.id)
        self.assertEqual(north_row["follow_up_request_id"], north_receipt.follow_up_request_id)
        self.assertTrue(north_row["unread"])
        self.assertEqual(north_row["branch_name"], self.north.name)
        self.assertEqual(north_row["lines"][0]["shipped"], 5)
        self.assertEqual(north_row["lines"][0]["received"], 4)
        self.assertEqual(north_row["lines"][0]["missing"], 1)
        self.assertTrue(north_row["reorder"])
        self.assertEqual(len(north_row["follow_up_lines"]), 1)
        self.assertEqual(north_row["follow_up_lines"][0]["quantity"], 1)
        south_row = next(row for row in payload["alerts"] if row["id"] == south_receipt.id)
        self.assertIsNone(south_row["follow_up_request_id"])
        self.assertFalse(south_row["reorder"])
        self.assertEqual(south_row["follow_up_lines"], [])

    def test_branch_list_is_scoped_and_other_branch_mark_read_404(self):
        north_req, north_gi, north_receipt = self._critical_receipt(
            self.north, self.operator, self.manager
        )
        south_op = _make_branch_user("alert-south-op2@example.com", self.south, ROLE_OPERATOR)
        _south_req, _south_gi, south_receipt = self._critical_receipt(
            self.south, south_op, self.other_manager, qty="3", received="2", reorder=False
        )
        self._login_branch(self.manager, self.north)
        page = self.client.get(reverse("branch_alerts_console"))
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, 'id="alerts-list"')
        response = self.client.get(reverse("branch_alerts_list"))
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        ids = [row["id"] for row in payload["alerts"]]
        self.assertEqual(ids, [north_receipt.id])
        self.assertEqual(payload["unread_count"], 1)
        row = payload["alerts"][0]
        self.assertEqual(row["request_id"], north_req.id)
        self.assertEqual(row["dispatch_id"], north_gi.id)
        self.assertEqual(row["follow_up_request_id"], north_receipt.follow_up_request_id)
        self.assertTrue(row["reorder"])
        self.assertEqual(len(row["follow_up_lines"]), 1)
        mark = self.client.post(reverse("branch_alerts_mark_read", args=[south_receipt.id]))
        self.assertEqual(mark.status_code, 404)

    def test_mark_read_is_per_user_and_keeps_row(self):
        _req, _gi, receipt = self._critical_receipt(self.north, self.operator, self.manager)
        self.client.force_login(self.wh_admin)
        self.assertEqual(services.unread_alert_count(self.wh_admin), 1)
        self.assertEqual(services.unread_alert_count(self.wh_manager_g2), 1)
        marked = self.client.post(reverse("manage_alerts_mark_read", args=[receipt.id]))
        self.assertEqual(marked.status_code, 200)
        self.assertFalse(marked.json()["unread"])
        self.assertTrue(
            BranchReceiptReadState.objects.filter(receipt=receipt, user=self.wh_admin).exists()
        )
        listed = self.client.get(reverse("manage_alerts_list")).json()
        self.assertEqual(listed["unread_count"], 0)
        self.assertEqual(listed["alerts"][0]["id"], receipt.id)
        self.assertFalse(listed["alerts"][0]["unread"])
        self.assertEqual(services.unread_alert_count(self.wh_manager_g2), 1)

    def test_page_load_does_not_mark_read(self):
        _req, _gi, receipt = self._critical_receipt(self.north, self.operator, self.manager)
        self.client.force_login(self.wh_manager_g2)
        self.client.get(reverse("warehouse_alerts_console"))
        self.assertEqual(services.unread_alert_count(self.wh_manager_g2), 1)
        self.assertFalse(
            BranchReceiptReadState.objects.filter(
                receipt=receipt, user=self.wh_manager_g2
            ).exists()
        )

    def test_warehouse_dashboard_shows_unread_badge(self):
        self._critical_receipt(self.north, self.operator, self.manager)
        self.client.force_login(self.wh_admin)
        response = self.client.get(reverse("staff_dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'href="/manage/alerts/"')
        self.assertContains(response, 'class="dash-card-badge"')
        self.assertContains(response, ">1</span>")

    def test_branch_dashboard_shows_unread_badge(self):
        self._critical_receipt(self.north, self.operator, self.manager)
        self._login_branch(self.manager, self.north)
        response = self.client.get(reverse("branch_dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'href="/branch/alerts/"')
        self.assertContains(response, 'class="dash-card-badge"')
        self.assertContains(response, ">1</span>")
