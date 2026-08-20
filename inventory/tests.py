import json
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.test import Client, TestCase
from django.urls import reverse

from accounts.groups import (
    GROUP_ADMINS,
    GROUP_MANAGERS,
    GROUP_OPERATORS,
    assign_warehouse_group,
)
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

from . import services
from .models import GoodsReceipt, GoodsReceiptLine, StockMovement


def make_warehouse_user(email, password="test-pass-123", group_name=GROUP_ADMINS):
    user = get_user_model().objects.create_user(email=email, password=password)
    assign_warehouse_group(user, group_name)
    return user


class InventoryTestCaseMixin:
    def setUp(self):
        self.user = make_warehouse_user("inv-admin@example.com")
        self.family = create_family("Test Family")
        self.vat_rate = VatRate.objects.get(code="VAT16")
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

    def test_adjust_stock_zero_is_rejected(self):
        with self.assertRaises(services.InvalidAdjustmentQuantityError):
            services.adjust_stock(self.item, "0", "noop", self.user)

    def test_receipt_summary_reports_remaining(self):
        po, line = self.create_approved_po("10")
        services.receive_goods(po, [{"line_id": line.id, "quantity_received": "4"}], self.user)

        summary = services.get_receipt_summary(po)
        self.assertEqual(len(summary), 1)
        self.assertEqual(summary[0]["quantity"], "10.000")
        self.assertEqual(summary[0]["received"], "4.000")
        self.assertEqual(summary[0]["remaining"], "6.000")


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
        self.assertEqual(resp.json()["quantity"], "5")

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

    def test_group_permissions_granted(self):
        admin = make_warehouse_user("perm-adm@example.com", group_name=GROUP_ADMINS)
        manager = make_warehouse_user("perm-mgr@example.com", group_name=GROUP_MANAGERS)
        operator = make_warehouse_user("perm-op@example.com", group_name=GROUP_OPERATORS)

        self.assertTrue(admin.has_perm("inventory.add_goodsreceipt"))
        self.assertTrue(admin.has_perm("inventory.can_adjust_stock"))
        self.assertTrue(manager.has_perm("inventory.add_goodsreceipt"))
        self.assertFalse(manager.has_perm("inventory.can_adjust_stock"))
        self.assertFalse(operator.has_perm("inventory.add_goodsreceipt"))
        self.assertTrue(operator.has_perm("inventory.view_goodsreceipt"))
