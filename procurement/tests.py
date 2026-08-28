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
    set_warehouse_grade,
)
from accounts.capabilities import can_approve_purchase_order, can_mutate_catalog
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


def make_warehouse_user(email, password="test-pass-123", group_name=GROUP_ADMINS, grade=1):
    user = get_user_model().objects.create_user(email=email, password=password)
    assign_warehouse_group(user, group_name)
    if grade != 1:
        set_warehouse_grade(user, grade)
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
            retail_price="1.00",
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

    def test_line_net_rounds_half_away_from_zero(self):
        po = self.create_draft_po()
        line = services.add_line(po, self.item, quantity="1", unit_cost="2.01")
        services.update_line(line, discount_commercial="50")
        line.refresh_from_db()

        # 2.01 * (1 - 0.50) = 1.005 → round half away from zero to 1.01 (not 1.00).
        self.assertEqual(line.net_unit_cost, Decimal("1.0050"))
        self.assertEqual(line.line_net, Decimal("1.01"))

    def test_line_vat_rounds_half_away_from_zero(self):
        po = self.create_draft_po()
        line = services.add_line(po, self.item, quantity="1", unit_cost="2.01")
        services.update_line(line, discount_commercial="50")
        line.vat_rate = Decimal("0.5000")
        line.save(update_fields=["vat_rate"])
        line.refresh_from_db()

        # 1.01 * 0.50 = 0.505 → round half away from zero to 0.51 (not 0.50).
        self.assertEqual(line.line_vat, Decimal("0.51"))

    def test_approve_rounds_totals_half_away_from_zero(self):
        po = self.create_draft_po()
        services.add_line(po, self.item, quantity="1", unit_cost="2.01")
        line = po.lines.get()
        services.update_line(line, discount_commercial="50")
        services.submit(po, self.user)

        po = services.approve(po, self.user)

        # net 1.005 → 1.01; VAT16 on 1.01 → 0.1616 → 0.16; gross 1.17
        self.assertEqual(po.approved_net, Decimal("1.01"))
        self.assertEqual(po.approved_vat, Decimal("0.16"))
        self.assertEqual(po.approved_gross, Decimal("1.17"))

    def test_negative_quantity_is_rejected(self):
        po = self.create_draft_po()
        with self.assertRaises(ValidationError):
            services.add_line(po, self.item, quantity="-1")

    def test_quantity_upper_bound_is_rejected(self):
        po = self.create_draft_po()
        with self.assertRaises(ValidationError) as ctx:
            services.add_line(po, self.item, quantity="1000000000")
        self.assertEqual(ctx.exception.code, "invalid_quantity")

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

    def test_update_line_rejects_over_precise_quantity(self):
        po = self.create_draft_po()
        line = services.add_line(po, self.item, quantity="1")
        with self.assertRaises(ValidationError):
            services.update_line(line, quantity="1.2345")

    def test_update_line_rejects_over_precise_unit_cost(self):
        po = self.create_draft_po()
        line = services.add_line(po, self.item, quantity="1")
        with self.assertRaises(ValidationError):
            services.update_line(line, unit_cost="1.999")

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

        po = services.reject(po, self.user, reason="Supplier lead time too long")

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
        po = services.reject(po, self.user, reason="Supplier lead time too long")
        self.assertEqual(po.status, PurchaseOrder.Status.REJECTED)

    def test_reopen_rejected_returns_to_draft_and_resubmit(self):
        po = self.create_draft_po()
        services.add_line(po, self.item, quantity="1")
        services.submit(po, self.user)
        po = services.reject(po, self.user, reason="Supplier lead time too long")
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

    def test_add_line_rejects_item_under_inactive_family(self):
        from products.services import update_family

        po = self.create_draft_po()
        update_family(self.family, is_active=False)
        with self.assertRaises(services.InactiveItemError):
            services.add_line(po, self.item, quantity="1")

    def test_submit_rejects_item_under_inactive_family(self):
        from products.services import update_family

        po = self.create_draft_po()
        services.add_line(po, self.item, quantity="1")
        update_family(self.family, is_active=False)
        with self.assertRaises(services.InactiveItemError):
            services.submit(po, self.user)

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
    def test_operator_grade_one_cannot_mutate(self):
        operator = make_warehouse_user("po-op@example.com", group_name=GROUP_OPERATORS)
        self.assertTrue(operator.has_perm("procurement.view_purchaseorder"))
        self.assertTrue(operator.has_perm("procurement.add_purchaseorder"))
        self.assertFalse(can_mutate_catalog(operator))
        self.assertFalse(can_approve_purchase_order(operator))

    def test_manager_grade_one_cannot_approve(self):
        manager = make_warehouse_user("po-mgr@example.com", group_name=GROUP_MANAGERS)
        self.assertTrue(manager.has_perm("procurement.add_purchaseorder"))
        self.assertTrue(manager.has_perm("procurement.can_approve"))
        self.assertTrue(can_mutate_catalog(manager))
        self.assertFalse(can_approve_purchase_order(manager))

    def test_admin_can_approve(self):
        admin = make_warehouse_user("po-adm@example.com", group_name=GROUP_ADMINS)
        self.assertTrue(admin.has_perm("procurement.can_approve"))
        self.assertTrue(can_approve_purchase_order(admin))


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

    def test_console_header_uses_settings_popover(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse("purchase_order_console"), **self.host)

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

    def test_approval_limits_page_uses_account_settings_gear(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse("approval_limit_console"), **self.host)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="settings-toggle"')
        self.assertContains(response, 'id="settings-popover"')
        self.assertNotContains(response, 'id="language-select"')
        self.assertNotContains(response, 'id="theme-toggle"')
        self.assertContains(response, self.user.email)
        self.assertContains(response, reverse("logout"))
        self.assertContains(response, 'id="settings-help"')

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

    def test_line_serializer_includes_line_vat(self):
        self.client.force_login(self.user)
        po = self._create_po_via_api()
        self.client.post(
            reverse("manage_purchase_order_lines", args=[po["id"]]),
            data=json.dumps({"item_id": self.item.id, "quantity": "10"}),
            content_type="application/json",
            **self.host,
        )

        resp = self.client.get(
            reverse("manage_purchase_order_lines", args=[po["id"]]),
            **self.host,
        )
        line = resp.json()["lines"][0]
        self.assertIn("line_vat", line)
        self.assertEqual(line["line_vat"], "20.00")

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
        reject = self.client.post(
            reverse("manage_purchase_order_reject", args=[po["id"]]),
            data=json.dumps({"reason": "Price too high"}),
            content_type="application/json",
            **self.host,
        )
        self.assertEqual(reject.status_code, 200)

        response = self.client.post(reverse("manage_purchase_order_reopen", args=[po["id"]]), **self.host)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["purchase_order"]["status"], "draft")

    def _approve_po_via_api(self, po_id):
        self.client.post(
            reverse("manage_purchase_order_lines", args=[po_id]),
            data=json.dumps({"item_id": self.item.id, "quantity": "1"}),
            content_type="application/json",
            **self.host,
        )
        self.client.post(reverse("manage_purchase_order_submit", args=[po_id]), **self.host)
        return self.client.post(
            reverse("manage_purchase_order_approve", args=[po_id]), **self.host
        )

    def test_cancel_approved_po_through_api(self):
        self.client.force_login(self.user)
        po = self._create_po_via_api()
        self._approve_po_via_api(po["id"])

        resp = self.client.post(
            reverse("manage_purchase_order_cancel", args=[po["id"]]),
            data=json.dumps({"reason": "Supplier cannot fulfil"}),
            content_type="application/json",
            **self.host,
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["purchase_order"]["status"], "cancelled")

    def test_cancel_draft_po_through_api(self):
        self.client.force_login(self.user)
        po = self._create_po_via_api()

        resp = self.client.post(
            reverse("manage_purchase_order_cancel", args=[po["id"]]),
            data=json.dumps({}),
            content_type="application/json",
            **self.host,
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["purchase_order"]["status"], "cancelled")

    def test_cancel_requires_reason_through_api(self):
        self.client.force_login(self.user)
        po = self._create_po_via_api()
        self._approve_po_via_api(po["id"])

        resp = self.client.post(
            reverse("manage_purchase_order_cancel", args=[po["id"]]),
            data=json.dumps({"reason": ""}),
            content_type="application/json",
            **self.host,
        )
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()["code"], "cancel_reason_required")

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


    def test_po_list_pagination(self):
        self.client.force_login(self.user)
        for _ in range(3):
            self._create_po_via_api()

        resp = self.client.get(
            reverse("manage_purchase_order_list") + "?page=1&page_size=2",
            **self.host,
        )
        self.assertEqual(resp.status_code, 200)
        payload = resp.json()
        self.assertEqual(len(payload["purchase_orders"]), 2)
        self.assertEqual(payload["total"], 3)
        self.assertEqual(payload["num_pages"], 2)

        page2 = self.client.get(
            reverse("manage_purchase_order_list") + "?page=2&page_size=2",
            **self.host,
        ).json()
        self.assertEqual(len(page2["purchase_orders"]), 1)

    def test_po_list_status_filter(self):
        self.client.force_login(self.user)
        self._create_po_via_api()  # stays draft
        po = self._create_po_via_api()
        self.client.post(
            reverse("manage_purchase_order_lines", args=[po["id"]]),
            data=json.dumps({"item_id": self.item.id, "quantity": "1"}),
            content_type="application/json",
            **self.host,
        )
        self.client.post(reverse("manage_purchase_order_submit", args=[po["id"]]), **self.host)

        submitted = self.client.get(
            reverse("manage_purchase_order_list") + "?status=submitted&page=1&page_size=50", **self.host
        ).json()
        self.assertEqual(submitted["total"], 1)
        drafts = self.client.get(
            reverse("manage_purchase_order_list") + "?status=draft&page=1&page_size=50", **self.host
        ).json()
        self.assertEqual(drafts["total"], 1)


class PurchaseOrderGradeAndAuditTests(PurchaseOrderTestCaseMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.client = Client()
        self.host = {"HTTP_HOST": "localhost"}

    def _submitted_po(self, user=None, quantity="1", unit_cost=None):
        creator = user or self.user
        po = services.create_purchase_order(self.supplier, creator)
        kwargs = {"quantity": quantity}
        if unit_cost is not None:
            kwargs["unit_cost"] = unit_cost
        services.add_line(po, self.item, **kwargs)
        return services.submit(po, creator)

    def test_operator_grade_two_can_submit_but_not_approve(self):
        operator = make_warehouse_user(
            "po-op-g2@example.com", group_name=GROUP_OPERATORS, grade=2
        )
        po = self._submitted_po(user=operator, quantity="1")
        with self.assertRaises(services.ApprovalDeniedError):
            services.approve(po, operator)

    def test_manager_grade_one_cannot_approve(self):
        manager = make_warehouse_user(
            "po-mgr-g1@example.com", group_name=GROUP_MANAGERS, grade=1
        )
        po = self._submitted_po(quantity="1")
        with self.assertRaises(services.ApprovalDeniedError):
            services.approve(po, manager)

    def test_manager_grade_two_self_approve_within_limit(self):
        manager = make_warehouse_user(
            "po-mgr-g2@example.com", group_name=GROUP_MANAGERS, grade=2
        )
        po = self._submitted_po(user=manager, quantity="1")
        _, _, gross = po.totals()
        self.assertLessEqual(gross, Decimal("100.00"))
        po = services.approve(po, manager)
        self.assertEqual(po.status, PurchaseOrder.Status.APPROVED)

    def test_manager_grade_two_self_approve_over_limit(self):
        manager = make_warehouse_user(
            "po-mgr-g2b@example.com", group_name=GROUP_MANAGERS, grade=2
        )
        po = self._submitted_po(user=manager, quantity="1", unit_cost="1000")
        _, _, gross = po.totals()
        self.assertGreater(gross, Decimal("100.00"))
        with self.assertRaises(services.SelfApprovalLimitError):
            services.approve(po, manager)

    def test_manager_grade_two_approves_others_within_limit(self):
        manager = make_warehouse_user(
            "po-mgr-g2c@example.com", group_name=GROUP_MANAGERS, grade=2
        )
        po = self._submitted_po(user=self.user, quantity="1", unit_cost="1000")
        _, _, gross = po.totals()
        self.assertGreater(gross, Decimal("100.00"))
        self.assertLessEqual(gross, Decimal("5000.00"))
        po = services.approve(po, manager)
        self.assertEqual(po.approved_by, manager)

    def test_manager_grade_two_others_over_limit(self):
        manager = make_warehouse_user(
            "po-mgr-g2d@example.com", group_name=GROUP_MANAGERS, grade=2
        )
        po = self._submitted_po(user=self.user, quantity="1", unit_cost="5000")
        _, _, gross = po.totals()
        self.assertGreater(gross, Decimal("5000.00"))
        with self.assertRaises(services.ApprovalLimitExceededError):
            services.approve(po, manager)

    def test_manager_grade_three_higher_cap(self):
        manager = make_warehouse_user(
            "po-mgr-g3@example.com", group_name=GROUP_MANAGERS, grade=3
        )
        po = self._submitted_po(user=self.user, quantity="1", unit_cost="5000")
        _, _, gross = po.totals()
        self.assertGreater(gross, Decimal("5000.00"))
        self.assertLessEqual(gross, Decimal("50000.00"))
        po = services.approve(po, manager)
        self.assertEqual(po.approved_by, manager)

    def test_admin_self_approves_with_no_cap(self):
        po = self._submitted_po(user=self.user, quantity="1", unit_cost="5000")
        po = services.approve(po, self.user)
        self.assertEqual(po.approved_by, self.user)

    def test_approve_rejects_totals_overflow(self):
        po = self._submitted_po(quantity="1000", unit_cost="9999999999.99")
        with self.assertRaises(services.ApprovalTotalOverflowError):
            services.approve(po, self.user)
        po.refresh_from_db()
        self.assertEqual(po.status, PurchaseOrder.Status.SUBMITTED)

    def test_approve_stores_optional_reason(self):
        po = self._submitted_po(quantity="1")
        po = services.approve(po, self.user, reason="OK to buy")
        log = po.change_logs.get(changes__has_key="approved_gross")
        self.assertEqual(log.reason, "OK to buy")

    def test_reject_requires_reason(self):
        po = self._submitted_po(quantity="1")
        with self.assertRaises(ValidationError) as ctx:
            services.reject(po, self.user, reason="   ")
        self.assertEqual(ctx.exception.code, "reject_reason_required")

    def test_reject_stores_reason(self):
        po = self._submitted_po(quantity="1")
        po = services.reject(po, self.user, reason="Duplicate order")
        log = po.change_logs.filter(
            action=PurchaseOrderChangeLog.Action.STATUS_CHANGED
        ).latest("created_at")
        self.assertEqual(log.reason, "Duplicate order")

    def test_close_partial_requires_reason(self):
        from inventory.services import receive_goods

        po = self._submitted_po(quantity="10")
        po = services.approve(po, self.user)
        line = po.lines.get()
        receive_goods(
            po,
            [{"line_id": line.id, "quantity_received": "4"}],
            self.user,
        )
        po.refresh_from_db()
        with self.assertRaises(ValidationError) as ctx:
            services.close(po, self.user, reason="")
        self.assertEqual(ctx.exception.code, "close_reason_required")

        po = services.close(po, self.user, reason="Supplier short shipped")
        log = po.change_logs.filter(
            action=PurchaseOrderChangeLog.Action.STATUS_CHANGED,
            changes__status__new=PurchaseOrder.Status.CLOSED,
        ).latest("created_at")
        self.assertEqual(log.reason, "Supplier short shipped")

    def test_full_receive_auto_close_reason(self):
        from inventory.services import receive_goods

        po = self._submitted_po(quantity="10")
        po = services.approve(po, self.user)
        line = po.lines.get()
        receive_goods(
            po,
            [{"line_id": line.id, "quantity_received": "10"}],
            self.user,
        )
        po.refresh_from_db()
        self.assertEqual(po.status, PurchaseOrder.Status.CLOSED)
        close_log = po.change_logs.filter(
            action=PurchaseOrderChangeLog.Action.STATUS_CHANGED,
            changes__status__new=PurchaseOrder.Status.CLOSED,
        ).latest("created_at")
        self.assertEqual(close_log.reason, "Fully received")
        receive_log = po.change_logs.filter(
            action=PurchaseOrderChangeLog.Action.STATUS_CHANGED,
            changes__status__new=PurchaseOrder.Status.RECEIVED,
        ).latest("created_at")
        self.assertEqual(receive_log.reason, "Goods received")

    def _approved_po(self, quantity="1"):
        po = self._submitted_po(quantity=quantity)
        return services.approve(po, self.user)

    def test_cancel_approved_po_with_no_receipts(self):
        po = self._approved_po()
        po = services.cancel(po, self.user, reason="Supplier cannot fulfil")

        self.assertEqual(po.status, PurchaseOrder.Status.CANCELLED)
        log = po.change_logs.filter(
            action=PurchaseOrderChangeLog.Action.STATUS_CHANGED,
            changes__status__new=PurchaseOrder.Status.CANCELLED,
        ).latest("created_at")
        self.assertEqual(log.reason, "Supplier cannot fulfil")

    def test_cancel_draft_po_no_reason(self):
        po = services.create_purchase_order(self.supplier, user=self.user)
        po = services.cancel(po, self.user)
        self.assertEqual(po.status, PurchaseOrder.Status.CANCELLED)
        log = po.change_logs.filter(
            action=PurchaseOrderChangeLog.Action.STATUS_CHANGED,
            changes__status__new=PurchaseOrder.Status.CANCELLED,
        ).latest("created_at")
        self.assertEqual(log.changes["status"]["old"], PurchaseOrder.Status.DRAFT)
        self.assertEqual(log.reason, "")

    def test_cancel_requires_reason(self):
        po = self._approved_po()
        with self.assertRaises(ValidationError) as ctx:
            services.cancel(po, self.user, reason="   ")
        self.assertEqual(ctx.exception.code, "cancel_reason_required")

    def test_cancel_submitted_is_invalid(self):
        po = self._submitted_po()
        with self.assertRaises(services.InvalidStatusTransitionError):
            services.cancel(po, self.user, reason="Changed my mind")

    def test_cancel_with_receipts_is_rejected(self):
        from inventory.models import GoodsReceipt, GoodsReceiptLine

        po = self._approved_po()
        line = po.lines.get()
        receipt = GoodsReceipt.objects.create(purchase_order=po, received_by=self.user)
        GoodsReceiptLine.objects.create(
            goods_receipt=receipt,
            purchase_order_line=line,
            quantity_received=Decimal("1"),
        )
        with self.assertRaises(services.PurchaseOrderCancelError):
            services.cancel(po, self.user, reason="Void")

    def test_notify_stub_runs_on_commit(self):
        from unittest.mock import patch

        po = self._submitted_po(quantity="1")
        with patch("procurement.services.notify_supplier_on_approval") as notify:
            with self.captureOnCommitCallbacks(execute=True):
                services.approve(po, self.user)
            notify.assert_called_once()

    def test_notify_stub_not_called_when_approve_fails(self):
        from unittest.mock import patch

        po = self.create_draft_po()
        services.add_line(po, self.item, quantity="1")
        with patch("procurement.services.notify_supplier_on_approval") as notify:
            with self.assertRaises(services.InvalidStatusTransitionError):
                services.approve(po, self.user)
            notify.assert_not_called()

    def test_manager_cannot_edit_approval_limits(self):
        manager = make_warehouse_user(
            "po-mgr-limits@example.com", group_name=GROUP_MANAGERS, grade=2
        )
        limit = services.list_approval_limits().get(grade=2)
        with self.assertRaises(services.ApprovalPolicyForbiddenError):
            services.update_approval_limit(
                limit, manager, self_approval_limit="50"
            )

    def test_admin_can_edit_approval_limits(self):
        limit = services.list_approval_limits().get(grade=2)
        updated = services.update_approval_limit(
            limit, self.user, self_approval_limit="75.00"
        )
        self.assertEqual(updated.self_approval_limit, Decimal("75.00"))
        self.assertTrue(updated.change_logs.exists())

    def test_approval_limits_api_get_and_admin_patch(self):
        self.client.force_login(self.user)
        listing = self.client.get(reverse("manage_approval_limit_list"), **self.host)
        self.assertEqual(listing.status_code, 200)
        self.assertTrue(listing.json()["can_edit"])
        limit_id = listing.json()["limits"][0]["id"]

        patched = self.client.patch(
            reverse("manage_approval_limit_detail", args=[limit_id]),
            data=json.dumps({"approval_limit": "6000.00"}),
            content_type="application/json",
            **self.host,
        )
        self.assertEqual(patched.status_code, 200)
        self.assertEqual(patched.json()["limit"]["approval_limit"], "6000.00")

        manager = make_warehouse_user(
            "po-mgr-api-limits@example.com", group_name=GROUP_MANAGERS, grade=2
        )
        self.client.force_login(manager)
        denied = self.client.patch(
            reverse("manage_approval_limit_detail", args=[limit_id]),
            data=json.dumps({"approval_limit": "1.00"}),
            content_type="application/json",
            **self.host,
        )
        self.assertEqual(denied.status_code, 403)
