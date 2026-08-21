import json
from decimal import Decimal
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.test import Client, TestCase
from django.urls import reverse

from accounts.groups import (
    GROUP_ADMINS,
    GROUP_MANAGERS,
    GROUP_OPERATORS,
    assign_warehouse_group,
)
from products.models import (
    FamilyChangeLog,
    FamilyProduct,
    Item,
    ItemChangeLog,
    Supplier,
    SupplierChangeLog,
    SupplierItemPrice,
    SupplierItemPriceChangeLog,
    VatRate,
)
from products.permissions import can_view_catalog
from products.services import (
    DeactivateReasonRequiredError,
    DuplicateFamilyNameError,
    DuplicateInternalCodeError,
    DuplicateSupplierItemPriceError,
    DuplicateSupplierNameError,
    FamilyNameRequiredError,
    InvalidCostPriceError,
    InvalidSupplierEmailError,
    ReactivateReasonRequiredError,
    SupplierNameRequiredError,
    _save_family,
    _save_item,
    _save_supplier,
    bulk_deactivate_items,
    bulk_reactivate_items,
    catalog_below_reorder,
    catalog_buying_price,
    create_family,
    create_item,
    create_supplier,
    create_supplier_item_price,
    deactivate_item,
    get_catalog,
    get_families,
    get_item_buying_price,
    get_items,
    get_supplier_history,
    get_supplier_item_price_history,
    get_supplier_item_prices,
    get_suppliers,
    reactivate_item,
    update_family,
    update_item,
    update_supplier,
    update_supplier_item_price,
    validate_internal_code_available,
)


def make_warehouse_user(email, password="test-pass-123", group_name=GROUP_ADMINS):
    user = get_user_model().objects.create_user(email=email, password=password)
    assign_warehouse_group(user, group_name)
    return user


class ItemTestCaseMixin:
    def create_test_family(self, name="Test Family"):
        return create_family(name)

    def create_test_item(self, user, family=None, active=True, **kwargs):
        if family is None:
            family = self.family
        if "vat_rate" not in kwargs:
            kwargs["vat_rate"] = VatRate.objects.get(code="VAT16")
        defaults = {
            "family": family,
            "description": "Test item",
            "unit_of_measure": Item.UnitOfMeasure.PIECE,
        }
        defaults.update(kwargs)
        item = create_item(user, **defaults)
        if active:
            reactivate_item(user, item, reason="Genesis")
            item.refresh_from_db()
        return item


class ItemServiceTests(ItemTestCaseMixin, TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            email="staff@example.com",
            password="test-pass-123",
        )
        self.family = self.create_test_family()
        self.vat_rate = VatRate.objects.get(code="VAT16")

    def test_create_item_writes_audit_log(self):
        item = create_item(
            self.user,
            family=self.family,
            description="Cement 50kg",
            internal_code="CEM-50",
            unit_of_measure=Item.UnitOfMeasure.KG,
            reorder_level="20",
            vat_rate=self.vat_rate,
            reason="Initial stocktake",
        )

        log = item.change_logs.get(action=ItemChangeLog.Action.CREATED)

        self.assertEqual(log.action, ItemChangeLog.Action.CREATED)
        self.assertEqual(log.user, self.user)
        self.assertEqual(log.reason, "Initial stocktake")
        self.assertEqual(log.changes["description"], "Cement 50kg")
        self.assertEqual(log.changes["family"]["name"], self.family.name)
        self.assertEqual(log.changes["unit_of_measure"], Item.UnitOfMeasure.KG)
        self.assertFalse(item.is_active)

    def test_create_item_starts_inactive(self):
        item = create_item(
            self.user,
            family=self.family,
            description="New item",
            unit_of_measure=Item.UnitOfMeasure.PIECE,
            vat_rate=self.vat_rate,
        )

        self.assertFalse(item.is_active)

    def test_update_item_detects_changes_after_in_memory_mutation(self):
        item = self.create_test_item(
            self.user,
            description="Original",
        )

        item.description = "Updated"
        update_item(
            self.user,
            item,
            description="Updated",
            reason="Corrected label",
        )

        item.refresh_from_db()
        self.assertEqual(item.description, "Updated")

        log = item.change_logs.latest("created_at")
        self.assertEqual(log.action, ItemChangeLog.Action.UPDATED)
        self.assertEqual(log.reason, "Corrected label")
        self.assertEqual(log.changes["description"]["old"], "Original")
        self.assertEqual(log.changes["description"]["new"], "Updated")

    def test_update_item_audits_family_and_reorder_level(self):
        other_family = self.create_test_family("Other Family")
        item = self.create_test_item(
            self.user,
            description="Item",
            reorder_level="0",
        )

        update_item(
            self.user,
            item,
            family=other_family,
            reorder_level=Decimal("15"),
            unit_of_measure=Item.UnitOfMeasure.KG,
        )

        log = item.change_logs.latest("created_at")
        self.assertEqual(log.changes["family"]["new"]["name"], "Other Family")
        self.assertEqual(log.changes["reorder_level"]["new"], "15")
        self.assertEqual(log.changes["unit_of_measure"]["new"], Item.UnitOfMeasure.KG)

    def test_get_items_active_only_excludes_deactivated(self):
        active = self.create_test_item(self.user, description="Active item")
        inactive = self.create_test_item(self.user, description="Inactive item")
        deactivate_item(self.user, inactive, reason="Removed from catalogue")

        active_ids = list(get_items().values_list("id", flat=True))
        all_ids = list(get_items(active_only=False).values_list("id", flat=True))

        self.assertEqual(active_ids, [active.id])
        self.assertEqual(sorted(all_ids), sorted([active.id, inactive.id]))

    def test_get_items_filters_by_family(self):
        pipes = self.create_test_family("Pipes")
        cement = self.create_test_family("Cement")
        pipe_item = self.create_test_item(
            self.user,
            family=pipes,
            internal_code="PIPE-1",
            description="Pipe",
        )
        self.create_test_item(
            self.user,
            family=cement,
            internal_code="CEM-1",
            description="Cement",
        )

        pipe_ids = list(get_items(family=pipes).values_list("id", flat=True))

        self.assertEqual(pipe_ids, [pipe_item.id])

    def test_duplicate_internal_code_is_rejected(self):
        self.create_test_item(
            self.user,
            description="First",
            internal_code="PIPE-20",
        )

        with self.assertRaises(DuplicateInternalCodeError):
            validate_internal_code_available("PIPE-20")

        with self.assertRaises(DuplicateInternalCodeError):
            self.create_test_item(
                self.user,
                description="Second",
                internal_code="PIPE-20",
            )

    def test_duplicate_internal_code_is_case_insensitive(self):
        self.create_test_item(
            self.user,
            description="First",
            internal_code="CASE-1",
        )

        with self.assertRaises(DuplicateInternalCodeError):
            self.create_test_item(
                self.user,
                description="Second",
                internal_code="case-1",
            )

    def test_update_item_rejects_duplicate_internal_code(self):
        self.create_test_item(
            self.user,
            description="First",
            internal_code="CODE-A",
        )
        second = self.create_test_item(
            self.user,
            description="Second",
            internal_code="CODE-B",
        )

        with self.assertRaises(DuplicateInternalCodeError):
            update_item(
                self.user,
                second,
                internal_code="CODE-A",
            )

    def test_deactivate_and_reactivate_write_audit_logs(self):
        item = self.create_test_item(self.user, description="Lifecycle item")

        deactivate_item(self.user, item, reason="End of line")
        item.refresh_from_db()
        self.assertFalse(item.is_active)

        deactivated_log = item.change_logs.latest("created_at")
        self.assertEqual(deactivated_log.action, ItemChangeLog.Action.DEACTIVATED)
        self.assertEqual(deactivated_log.reason, "End of line")

        reactivate_item(self.user, item, reason="Back in stock")
        item.refresh_from_db()
        self.assertTrue(item.is_active)

        reactivated_log = item.change_logs.latest("created_at")
        self.assertEqual(reactivated_log.action, ItemChangeLog.Action.REACTIVATED)
        self.assertEqual(reactivated_log.reason, "Back in stock")

    def test_deactivate_item_requires_reason(self):
        item = self.create_test_item(self.user, description="Needs a reason")

        with self.assertRaises(DeactivateReasonRequiredError):
            deactivate_item(self.user, item)

        with self.assertRaises(DeactivateReasonRequiredError):
            deactivate_item(self.user, item, reason="   ")

        item.refresh_from_db()
        self.assertTrue(item.is_active)

    def test_reactivate_item_requires_reason(self):
        item = create_item(
            self.user,
            family=self.family,
            description="Needs activation reason",
            unit_of_measure=Item.UnitOfMeasure.PIECE,
            vat_rate=self.vat_rate,
        )

        with self.assertRaises(ReactivateReasonRequiredError):
            reactivate_item(self.user, item)

        with self.assertRaises(ReactivateReasonRequiredError):
            reactivate_item(self.user, item, reason="   ")

        item.refresh_from_db()
        self.assertFalse(item.is_active)

    def test_reactivate_already_active_does_not_require_reason(self):
        item = self.create_test_item(self.user, description="Already active")

        reactivate_item(self.user, item)

        item.refresh_from_db()
        self.assertTrue(item.is_active)
        self.assertEqual(
            item.change_logs.filter(action=ItemChangeLog.Action.REACTIVATED).count(),
            1,
        )

    def test_deactivate_already_inactive_does_not_require_reason(self):
        item = self.create_test_item(self.user, description="Already hidden")
        deactivate_item(self.user, item, reason="End of line")

        deactivate_item(self.user, item)

        item.refresh_from_db()
        self.assertFalse(item.is_active)
        self.assertEqual(
            item.change_logs.filter(action=ItemChangeLog.Action.DEACTIVATED).count(),
            1,
        )


class FamilyProductServiceTests(TestCase):
    def test_get_families_active_only_excludes_inactive(self):
        active = create_family("Active Family")
        inactive = create_family("Inactive Family")
        update_family(inactive, is_active=False)

        names = list(get_families().values_list("name", flat=True))

        self.assertEqual(names, ["Active Family"])

    def test_update_family_changes_name(self):
        family = create_family("Original")

        updated = update_family(family, name="Renamed")

        self.assertEqual(updated.name, "Renamed")

    def test_create_family_respects_is_active(self):
        inactive = create_family("Inactive on create", is_active=False)

        self.assertFalse(inactive.is_active)
        self.assertEqual(get_families(active_only=False).count(), 1)
        self.assertEqual(get_families().count(), 0)

    def test_create_family_rejects_empty_name(self):
        with self.assertRaises(FamilyNameRequiredError):
            create_family("   ")

        self.assertEqual(get_families(active_only=False).count(), 0)

    def test_create_family_rejects_duplicate_name(self):
        create_family("Cement")

        with self.assertRaises(DuplicateFamilyNameError):
            create_family("Cement")

        with self.assertRaises(DuplicateFamilyNameError):
            create_family("cement")

        with self.assertRaises(DuplicateFamilyNameError):
            create_family("CEMENT")

        self.assertEqual(get_families(active_only=False).count(), 1)

    def test_update_family_rejects_duplicate_name(self):
        create_family("Cement")
        pipes = create_family("Pipes")

        with self.assertRaises(DuplicateFamilyNameError):
            update_family(pipes, name="cement")

        pipes.refresh_from_db()
        self.assertEqual(pipes.name, "Pipes")

    def test_update_family_allows_unchanged_name(self):
        family = create_family("Cement")

        updated = update_family(family, name="Cement", is_active=False)

        self.assertEqual(updated.name, "Cement")
        self.assertFalse(updated.is_active)

    def test_create_family_writes_audit_log(self):
        user_model = get_user_model()
        user = user_model.objects.create_user(
            email="staff@example.com",
            password="test-pass-123",
        )

        family = create_family("Cement", user=user)

        log = family.change_logs.get(action=FamilyChangeLog.Action.CREATED)
        self.assertEqual(log.user, user)
        self.assertEqual(log.changes["name"], "Cement")
        self.assertTrue(log.changes["is_active"])

    def test_create_family_allows_null_user(self):
        family = create_family("Cement")

        log = family.change_logs.get(action=FamilyChangeLog.Action.CREATED)
        self.assertIsNone(log.user)

    def test_update_family_writes_updated_log(self):
        family = create_family("Original")

        update_family(family, name="Renamed")

        log = family.change_logs.get(action=FamilyChangeLog.Action.UPDATED)
        self.assertEqual(log.changes["name"]["old"], "Original")
        self.assertEqual(log.changes["name"]["new"], "Renamed")

    def test_deactivate_and_reactivate_family_write_lifecycle_logs(self):
        family = create_family("Cement")

        update_family(family, is_active=False)
        deactivated = family.change_logs.get(action=FamilyChangeLog.Action.DEACTIVATED)
        self.assertEqual(deactivated.changes, {})

        update_family(family, is_active=True)
        reactivated = family.change_logs.get(action=FamilyChangeLog.Action.REACTIVATED)
        self.assertEqual(reactivated.changes, {})

    def test_unchanged_family_update_does_not_write_audit_log(self):
        family = create_family("Cement")

        update_family(family, name="Cement", is_active=True)

        self.assertEqual(family.change_logs.count(), 1)
        self.assertEqual(
            family.change_logs.get().action,
            FamilyChangeLog.Action.CREATED,
        )


class ItemPermissionTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.warehouse_user = make_warehouse_user("warehouse@example.com")
        self.plain_user = user_model.objects.create_user(
            email="user@example.com",
            password="test-pass-123",
        )
        self.staff_user = user_model.objects.create_user(
            email="staff@example.com",
            password="test-pass-123",
            is_staff=True,
        )

    def test_can_view_catalog_requires_warehouse_view_permission(self):
        self.assertTrue(can_view_catalog(self.warehouse_user))
        self.assertFalse(can_view_catalog(self.plain_user))
        self.assertFalse(can_view_catalog(self.staff_user))

    def test_superuser_can_view_catalog(self):
        superuser = get_user_model().objects.create_superuser(
            email="super@example.com",
            password="test-pass-123",
        )
        self.assertTrue(can_view_catalog(superuser))

    def test_anonymous_user_cannot_view_catalog(self):
        anonymous = get_user_model()()
        self.assertFalse(can_view_catalog(anonymous))


class ItemAdminAccessTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.superuser = user_model.objects.create_superuser(
            email="super@example.com",
            password="test-pass-123",
        )
        self.warehouse_user = make_warehouse_user("warehouse@example.com")
        self.staff_user = user_model.objects.create_user(
            email="staff@example.com",
            password="test-pass-123",
            is_staff=True,
        )
        self.client = Client()
        self.changelist_url = reverse("admin:products_item_changelist")

    def test_superuser_can_open_item_admin(self):
        self.client.force_login(self.superuser)

        response = self.client.get(self.changelist_url)

        self.assertEqual(response.status_code, 200)

    def test_warehouse_user_cannot_open_item_admin(self):
        self.client.force_login(self.warehouse_user)

        response = self.client.get(self.changelist_url)

        self.assertIn(response.status_code, (302, 403))

    def test_staff_non_superuser_cannot_open_item_admin(self):
        self.client.force_login(self.staff_user)

        response = self.client.get(self.changelist_url)

        self.assertIn(response.status_code, (302, 403))


class FamilyProductAdminAccessTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.superuser = user_model.objects.create_superuser(
            email="super@example.com",
            password="test-pass-123",
        )
        self.warehouse_user = make_warehouse_user("warehouse@example.com")
        self.client = Client()
        self.family_changelist_url = reverse("admin:products_familyproduct_changelist")

    def test_superuser_can_open_family_admin(self):
        self.client.force_login(self.superuser)

        response = self.client.get(self.family_changelist_url)

        self.assertEqual(response.status_code, 200)

    def test_warehouse_user_cannot_open_family_admin(self):
        self.client.force_login(self.warehouse_user)

        response = self.client.get(self.family_changelist_url)

        self.assertIn(response.status_code, (302, 403))

    def test_admin_create_rejects_duplicate_family_name(self):
        create_family("Cement")
        self.client.force_login(self.superuser)

        response = self.client.post(
            reverse("admin:products_familyproduct_add"),
            {"name": "cement", "is_active": "on", "_save": "Save"},
        )

        self.assertEqual(response.status_code, 200)
        form = response.context["adminform"].form
        self.assertFormError(
            form,
            "name",
            'Family name "cement" is already used.',
        )
        self.assertEqual(
            FamilyProduct.objects.filter(name__iexact="Cement").count(),
            1,
        )


class SupplierServiceTests(TestCase):
    def setUp(self):
        self.staff_user = get_user_model().objects.create_user(
            email="staff@example.com",
            password="test-pass-123",
        )

    def test_update_supplier_changes_contact_fields(self):
        supplier = create_supplier(name="BuildSupply Ltd")

        updated = update_supplier(
            supplier,
            contact_name="Ana Ribeiro",
            phone="+351 210 000 001",
        )

        self.assertEqual(updated.contact_name, "Ana Ribeiro")
        self.assertEqual(updated.phone, "+351 210 000 001")

    def test_get_suppliers_active_only_excludes_inactive(self):
        active = create_supplier(name="Active Supplier")
        inactive = create_supplier(name="Inactive Supplier")
        update_supplier(inactive, is_active=False)

        names = list(get_suppliers().values_list("name", flat=True))

        self.assertEqual(names, ["Active Supplier"])

    def test_create_supplier_rejects_empty_name(self):
        with self.assertRaises(SupplierNameRequiredError):
            create_supplier("   ")

        self.assertEqual(get_suppliers(active_only=False).count(), 0)

    def test_create_supplier_rejects_duplicate_name_case_insensitive(self):
        create_supplier(name="BuildSupply Ltd")

        with self.assertRaises(DuplicateSupplierNameError):
            create_supplier(name="BuildSupply Ltd")

        with self.assertRaises(DuplicateSupplierNameError):
            create_supplier(name="buildsupply ltd")

        self.assertEqual(get_suppliers(active_only=False).count(), 1)

    def test_create_supplier_rejects_invalid_email(self):
        with self.assertRaises(InvalidSupplierEmailError):
            create_supplier(name="BuildSupply Ltd", email="not-an-email")

    def test_create_supplier_respects_is_active(self):
        inactive = create_supplier(name="Inactive on create", is_active=False)

        self.assertFalse(inactive.is_active)
        self.assertEqual(get_suppliers(active_only=False).count(), 1)
        self.assertEqual(get_suppliers().count(), 0)
        self.assertEqual(inactive.change_logs.count(), 1)
        log = inactive.change_logs.get(action=SupplierChangeLog.Action.CREATED)
        self.assertFalse(log.changes["is_active"])

    def test_create_supplier_writes_audit_log(self):
        supplier = create_supplier(
            name="BuildSupply Ltd",
            phone="+351 210 000 001",
            user=self.staff_user,
        )

        log = supplier.change_logs.get(action=SupplierChangeLog.Action.CREATED)
        self.assertEqual(log.user, self.staff_user)
        self.assertEqual(log.changes["name"], "BuildSupply Ltd")
        self.assertEqual(log.changes["phone"], "+351 210 000 001")
        self.assertTrue(log.changes["is_active"])

    def test_update_supplier_writes_updated_log(self):
        supplier = create_supplier(name="BuildSupply Ltd")

        update_supplier(
            supplier,
            user=self.staff_user,
            contact_name="Ana Ribeiro",
            phone="+351 210 000 001",
        )

        log = supplier.change_logs.get(action=SupplierChangeLog.Action.UPDATED)
        self.assertEqual(log.user, self.staff_user)
        self.assertEqual(log.changes["contact_name"]["new"], "Ana Ribeiro")
        self.assertEqual(log.changes["phone"]["new"], "+351 210 000 001")
        self.assertNotIn("name", log.changes)

    def test_deactivate_and_reactivate_supplier_write_lifecycle_logs(self):
        supplier = create_supplier(name="BuildSupply Ltd")

        update_supplier(supplier, is_active=False)
        deactivated = supplier.change_logs.get(
            action=SupplierChangeLog.Action.DEACTIVATED,
        )
        self.assertEqual(deactivated.changes, {})

        update_supplier(supplier, is_active=True)
        reactivated = supplier.change_logs.get(
            action=SupplierChangeLog.Action.REACTIVATED,
        )
        self.assertEqual(reactivated.changes, {})

    def test_get_supplier_history_returns_newest_first(self):
        supplier = create_supplier(name="BuildSupply Ltd")
        update_supplier(supplier, phone="+351 210 000 001")

        actions = list(get_supplier_history(supplier).values_list("action", flat=True))

        self.assertEqual(
            actions,
            [
                SupplierChangeLog.Action.UPDATED,
                SupplierChangeLog.Action.CREATED,
            ],
        )


class SupplierAdminAccessTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.superuser = user_model.objects.create_superuser(
            email="super@example.com",
            password="test-pass-123",
        )
        self.warehouse_user = make_warehouse_user("warehouse@example.com")
        self.client = Client()
        self.supplier_changelist_url = reverse("admin:products_supplier_changelist")

    def test_superuser_can_open_supplier_admin(self):
        self.client.force_login(self.superuser)

        response = self.client.get(self.supplier_changelist_url)

        self.assertEqual(response.status_code, 200)

    def test_warehouse_user_cannot_open_supplier_admin(self):
        self.client.force_login(self.warehouse_user)

        response = self.client.get(self.supplier_changelist_url)

        self.assertIn(response.status_code, (302, 403))

    def test_admin_create_rejects_duplicate_supplier_name(self):
        create_supplier("BuildSupply Ltd")
        self.client.force_login(self.superuser)

        response = self.client.post(
            reverse("admin:products_supplier_add"),
            {"name": "buildsupply ltd", "is_active": "on", "_save": "Save"},
        )

        self.assertEqual(response.status_code, 200)
        form = response.context["adminform"].form
        self.assertFormError(
            form,
            "name",
            'Supplier name "buildsupply ltd" is already used.',
        )
        self.assertEqual(
            Supplier.objects.filter(name__iexact="BuildSupply Ltd").count(),
            1,
        )


class ItemConsoleTests(ItemTestCaseMixin, TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.staff_user = make_warehouse_user("warehouse@example.com")
        self.non_staff_user = user_model.objects.create_user(
            email="user@example.com",
            password="test-pass-123",
        )
        self.client = Client()
        self.family = self.create_test_family()
        self.vat_rate = VatRate.objects.get(code="VAT16")

    def test_staff_can_open_console(self):
        self.client.force_login(self.staff_user)

        response = self.client.get(reverse("item_console"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "item-form")
        self.assertContains(response, "item-table-body")
        self.assertContains(response, "supplier-table-body")
        self.assertContains(response, "colVatRate")
        self.assertNotContains(response, "product-table-body")
        self.assertNotContains(response, "colPrice")
        self.assertNotContains(response, "colStock")

    def test_staff_can_open_dashboard(self):
        self.client.force_login(self.staff_user)

        response = self.client.get(reverse("staff_dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "/manage/items/")
        self.assertContains(response, "/api/manage/suppliers/")
        self.assertNotContains(response, 'href="/admin/"')
        self.assertNotContains(response, "/api/items/")
        self.assertContains(response, self.staff_user.email)
        self.assertContains(response, "warehouse_admins")
        self.assertContains(response, "products.view_item")
        self.assertContains(response, "products.delete_item")

    def test_anonymous_user_is_redirected_from_dashboard(self):
        response = self.client.get(reverse("staff_dashboard"))

        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response.url)

    def test_non_staff_user_cannot_open_dashboard(self):
        self.client.force_login(self.non_staff_user)

        response = self.client.get(reverse("staff_dashboard"))

        self.assertEqual(response.status_code, 403)

    def test_non_staff_user_cannot_open_console(self):
        self.client.force_login(self.non_staff_user)

        response = self.client.get(reverse("item_console"))

        self.assertEqual(response.status_code, 403)

    def test_anonymous_user_is_redirected_to_login(self):
        response = self.client.get(reverse("item_console"))

        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response.url)

    def test_staff_login_redirects_to_dashboard(self):
        response = self.client.post(
            reverse("login"),
            {"username": "warehouse@example.com", "password": "test-pass-123"},
        )

        self.assertRedirects(response, reverse("staff_dashboard"))

    def test_non_staff_user_cannot_use_manage_api(self):
        self.client.force_login(self.non_staff_user)

        response = self.client.get(reverse("manage_item_list"))

        self.assertEqual(response.status_code, 403)

    def test_operator_can_read_manage_api_but_cannot_create(self):
        operator = make_warehouse_user(
            "operator@example.com",
            group_name=GROUP_OPERATORS,
        )
        self.client.force_login(operator)

        listing = self.client.get(reverse("manage_item_list"))
        self.assertEqual(listing.status_code, 200)

        created = self.client.post(
            reverse("manage_item_list"),
            data=json.dumps({
                "family_id": self.family.id,
                "description": "Operator should not create",
                "unit_of_measure": Item.UnitOfMeasure.PIECE,
                "vat_rate_id": self.vat_rate.id,
            }),
            content_type="application/json",
        )
        self.assertEqual(created.status_code, 403)
        self.assertEqual(
            created.json()["error"],
            "Missing permission: products.add_item",
        )

    def test_operator_console_page_hides_write_flags(self):
        operator = make_warehouse_user(
            "operator-ui@example.com",
            group_name=GROUP_OPERATORS,
        )
        self.client.force_login(operator)

        response = self.client.get(reverse("item_console"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-can-add-item="false"')
        self.assertContains(response, 'data-can-change-item="false"')
        self.assertContains(response, 'data-can-add-family="false"')
        self.assertContains(response, 'data-can-change-family="false"')
        self.assertContains(response, 'data-can-add-supplier="false"')
        self.assertContains(response, 'data-can-change-supplier="false"')

    def test_operator_manage_api_reports_read_only_permissions(self):
        operator = make_warehouse_user(
            "operator-perms@example.com",
            group_name=GROUP_OPERATORS,
        )
        self.client.force_login(operator)

        payload = self.client.get(reverse("manage_item_list")).json()

        self.assertEqual(
            payload["permissions"],
            {
                "add_item": False,
                "change_item": False,
                "add_family": False,
                "change_family": False,
                "add_supplier": False,
                "change_supplier": False,
                "add_supplier_item_price": False,
                "change_supplier_item_price": False,
            },
        )

    def test_admin_console_page_shows_write_flags(self):
        self.client.force_login(self.staff_user)

        response = self.client.get(reverse("item_console"))

        self.assertContains(response, 'data-can-add-item="true"')
        self.assertContains(response, 'data-can-change-item="true"')
        self.assertContains(response, 'data-can-add-family="true"')
        self.assertContains(response, 'data-can-change-family="true"')
        self.assertContains(response, 'data-can-add-supplier="true"')
        self.assertContains(response, 'data-can-change-supplier="true"')

    def test_admin_manage_api_reports_write_permissions(self):
        self.client.force_login(self.staff_user)

        payload = self.client.get(reverse("manage_item_list")).json()

        self.assertEqual(
            payload["permissions"],
            {
                "add_item": True,
                "change_item": True,
                "add_family": True,
                "change_family": True,
                "add_supplier": True,
                "change_supplier": True,
                "add_supplier_item_price": True,
                "change_supplier_item_price": True,
            },
        )

    def test_staff_manage_api_includes_inactive_items(self):
        active = self.create_test_item(self.staff_user, description="Visible")
        inactive = self.create_test_item(
            self.staff_user,
            description="Hidden",
            active=False,
        )
        self.client.force_login(self.staff_user)

        response = self.client.get(reverse("manage_item_list"))

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        item_ids = [item["id"] for item in payload["items"]]
        self.assertEqual(sorted(item_ids), sorted([active.id, inactive.id]))
        self.assertIn("families", payload)
        self.assertNotIn("suppliers", payload)

    def test_manage_api_supports_pagination(self):
        for index in range(5):
            self.create_test_item(self.staff_user, description=f"Item {index}")
        self.client.force_login(self.staff_user)

        page1 = self.client.get(
            reverse("manage_item_list"),
            {"page": "1", "page_size": "2"},
        )
        self.assertEqual(page1.status_code, 200)
        payload = page1.json()
        self.assertEqual(len(payload["items"]), 2)
        self.assertEqual(payload["total"], 5)
        self.assertEqual(payload["page"], 1)
        self.assertEqual(payload["page_size"], 2)
        self.assertEqual(payload["num_pages"], 3)

        page3 = self.client.get(
            reverse("manage_item_list"),
            {"page": "3", "page_size": "2"},
        )
        self.assertEqual(len(page3.json()["items"]), 1)

    def test_staff_can_create_and_update_item_through_console_api(self):
        self.client.force_login(self.staff_user)

        create_response = self.client.post(
            reverse("manage_item_list"),
            data=json.dumps({
                "family_id": self.family.id,
                "description": "Console cement",
                "unit_of_measure": Item.UnitOfMeasure.KG,
                "internal_code": "CON-1",
                "reorder_level": "4",
                "vat_rate_id": self.vat_rate.id,
                "reason": "Added from console",
            }),
            content_type="application/json",
        )

        self.assertEqual(create_response.status_code, 200)
        created = create_response.json()["item"]
        item = Item.objects.get(pk=created["id"])
        self.assertFalse(item.is_active)
        self.assertEqual(item.description, "Console cement")
        self.assertNotIn("stock", created)
        self.assertNotIn("suppliers", created)
        self.assertEqual(
            item.change_logs.latest("created_at").reason,
            "Added from console",
        )

        activate_response = self.client.post(
            reverse("manage_item_reactivate", args=[item.id]),
            data=json.dumps({"reason": "Genesis"}),
            content_type="application/json",
        )
        self.assertEqual(activate_response.status_code, 200)
        item.refresh_from_db()
        self.assertTrue(item.is_active)

        update_response = self.client.patch(
            reverse("manage_item_detail", args=[item.id]),
            data=json.dumps({
                "description": "Console cement updated",
                "reason": "Corrected label",
            }),
            content_type="application/json",
        )

        self.assertEqual(update_response.status_code, 200)
        item.refresh_from_db()
        self.assertEqual(item.description, "Console cement updated")
        self.assertEqual(
            item.change_logs.latest("created_at").reason,
            "Corrected label",
        )

    def test_staff_can_deactivate_through_console_api(self):
        item = self.create_test_item(self.staff_user, description="To hide")
        self.client.force_login(self.staff_user)

        response = self.client.post(
            reverse("manage_item_deactivate", args=[item.id]),
            data=json.dumps({"reason": "End of line"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        item.refresh_from_db()
        self.assertFalse(item.is_active)
        self.assertEqual(
            item.change_logs.latest("created_at").action,
            ItemChangeLog.Action.DEACTIVATED,
        )

    def test_console_deactivate_without_reason_is_rejected(self):
        item = self.create_test_item(self.staff_user, description="To hide")
        self.client.force_login(self.staff_user)

        response = self.client.post(
            reverse("manage_item_deactivate", args=[item.id]),
            data=json.dumps({"reason": ""}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        payload = response.json()
        self.assertEqual(payload["code"], "deactivate_reason_required")
        item.refresh_from_db()
        self.assertTrue(item.is_active)

    def test_console_reactivate_without_reason_is_rejected(self):
        item = self.create_test_item(
            self.staff_user,
            description="Inactive item",
            active=False,
        )
        self.client.force_login(self.staff_user)

        response = self.client.post(
            reverse("manage_item_reactivate", args=[item.id]),
            data=json.dumps({"reason": ""}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        payload = response.json()
        self.assertEqual(payload["code"], "reactivate_reason_required")
        item.refresh_from_db()
        self.assertFalse(item.is_active)

    def test_console_bulk_deactivate_without_reason_is_rejected(self):
        item = self.create_test_item(self.staff_user, description="To hide")
        self.client.force_login(self.staff_user)

        response = self.client.post(
            reverse("manage_item_bulk"),
            data=json.dumps({
                "action": "deactivate",
                "ids": [item.id],
                "reason": "",
            }),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["code"], "deactivate_reason_required")
        item.refresh_from_db()
        self.assertTrue(item.is_active)

    def test_staff_can_create_family_through_console_api(self):
        self.client.force_login(self.staff_user)

        response = self.client.post(
            reverse("manage_family_list"),
            data=json.dumps({"name": "Pipes"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()["family"]
        self.assertEqual(payload["name"], "Pipes")
        self.assertTrue(payload["is_active"])
        self.assertEqual(payload["item_count"], 0)

        list_response = self.client.get(reverse("manage_family_list"))
        names = [family["name"] for family in list_response.json()["families"]]
        self.assertIn("Pipes", names)

    def test_console_create_family_rejects_empty_and_duplicate_name(self):
        self.client.force_login(self.staff_user)

        empty = self.client.post(
            reverse("manage_family_list"),
            data=json.dumps({"name": "  "}),
            content_type="application/json",
        )
        self.assertEqual(empty.status_code, 400)
        self.assertEqual(empty.json()["code"], "family_name_required")

        self.client.post(
            reverse("manage_family_list"),
            data=json.dumps({"name": "Cement"}),
            content_type="application/json",
        )
        duplicate = self.client.post(
            reverse("manage_family_list"),
            data=json.dumps({"name": "Cement"}),
            content_type="application/json",
        )
        self.assertEqual(duplicate.status_code, 400)
        self.assertEqual(duplicate.json()["code"], "duplicate_family_name")

        duplicate_case = self.client.post(
            reverse("manage_family_list"),
            data=json.dumps({"name": "cement"}),
            content_type="application/json",
        )
        self.assertEqual(duplicate_case.status_code, 400)
        self.assertEqual(duplicate_case.json()["code"], "duplicate_family_name")

    def test_staff_can_rename_and_deactivate_family_through_console_api(self):
        family = self.create_test_family("Original")
        self.client.force_login(self.staff_user)

        rename = self.client.patch(
            reverse("manage_family_detail", args=[family.id]),
            data=json.dumps({"name": "Renamed"}),
            content_type="application/json",
        )
        self.assertEqual(rename.status_code, 200)
        self.assertEqual(rename.json()["family"]["name"], "Renamed")

        deactivate = self.client.patch(
            reverse("manage_family_detail", args=[family.id]),
            data=json.dumps({"is_active": False}),
            content_type="application/json",
        )
        self.assertEqual(deactivate.status_code, 200)
        family.refresh_from_db()
        self.assertFalse(family.is_active)

    def test_console_family_payload_includes_item_count(self):
        self.create_test_item(self.staff_user, description="Counted")
        self.client.force_login(self.staff_user)

        response = self.client.get(reverse("manage_item_list"))

        families = {item["name"]: item for item in response.json()["families"]}
        self.assertEqual(families[self.family.name]["item_count"], 1)

    def test_staff_can_create_item_with_newly_created_family(self):
        self.client.force_login(self.staff_user)
        family_response = self.client.post(
            reverse("manage_family_list"),
            data=json.dumps({"name": "New Line"}),
            content_type="application/json",
        )
        family_id = family_response.json()["family"]["id"]

        item_response = self.client.post(
            reverse("manage_item_list"),
            data=json.dumps({
                "family_id": family_id,
                "description": "Family-first item",
                "unit_of_measure": Item.UnitOfMeasure.PIECE,
                "vat_rate_id": self.vat_rate.id,
            }),
            content_type="application/json",
        )

        self.assertEqual(item_response.status_code, 200)
        item = Item.objects.get(pk=item_response.json()["item"]["id"])
        self.assertEqual(item.family_id, family_id)
        self.assertFalse(item.is_active)

    def test_non_staff_user_cannot_use_family_api(self):
        self.client.force_login(self.non_staff_user)

        response = self.client.get(reverse("manage_family_list"))

        self.assertEqual(response.status_code, 403)

    def test_console_family_create_and_deactivate_write_audit_history(self):
        self.client.force_login(self.staff_user)

        create_response = self.client.post(
            reverse("manage_family_list"),
            data=json.dumps({"name": "Pipes"}),
            content_type="application/json",
        )
        family_id = create_response.json()["family"]["id"]

        self.client.patch(
            reverse("manage_family_detail", args=[family_id]),
            data=json.dumps({"is_active": False}),
            content_type="application/json",
        )

        history = self.client.get(
            reverse("manage_family_history", args=[family_id]),
        )
        self.assertEqual(history.status_code, 200)
        by_action = {entry["action"]: entry for entry in history.json()["history"]}
        self.assertEqual(set(by_action), {"created", "deactivated"})
        self.assertEqual(by_action["created"]["user_email"], self.staff_user.email)

        family = FamilyProduct.objects.get(pk=family_id)
        self.assertEqual(
            family.change_logs.get(action=FamilyChangeLog.Action.CREATED).user,
            self.staff_user,
        )

    def test_non_staff_user_cannot_use_family_history_api(self):
        family = self.create_test_family("Pipes")
        self.client.force_login(self.non_staff_user)

        response = self.client.get(
            reverse("manage_family_history", args=[family.id]),
        )

        self.assertEqual(response.status_code, 403)

    def test_staff_can_create_and_update_supplier_through_console_api(self):
        self.client.force_login(self.staff_user)

        create_response = self.client.post(
            reverse("manage_supplier_list"),
            data=json.dumps({
                "name": "BuildSupply Ltd",
                "contact_name": "Ana Ribeiro",
                "email": "sales@buildsupply.dev",
            }),
            content_type="application/json",
        )

        self.assertEqual(create_response.status_code, 200)
        payload = create_response.json()["supplier"]
        self.assertEqual(payload["name"], "BuildSupply Ltd")
        self.assertTrue(payload["is_active"])
        self.assertNotIn("suppliers", self.client.get(reverse("manage_item_list")).json())

        update_response = self.client.patch(
            reverse("manage_supplier_detail", args=[payload["id"]]),
            data=json.dumps({"phone": "+351 210 000 001"}),
            content_type="application/json",
        )
        self.assertEqual(update_response.status_code, 200)
        self.assertEqual(update_response.json()["supplier"]["phone"], "+351 210 000 001")

        list_response = self.client.get(reverse("manage_supplier_list"))
        names = [item["name"] for item in list_response.json()["suppliers"]]
        self.assertIn("BuildSupply Ltd", names)

    def test_console_create_supplier_rejects_empty_and_duplicate_name(self):
        self.client.force_login(self.staff_user)

        empty = self.client.post(
            reverse("manage_supplier_list"),
            data=json.dumps({"name": "  "}),
            content_type="application/json",
        )
        self.assertEqual(empty.status_code, 400)
        self.assertEqual(empty.json()["code"], "supplier_name_required")

        self.client.post(
            reverse("manage_supplier_list"),
            data=json.dumps({"name": "BuildSupply Ltd"}),
            content_type="application/json",
        )
        duplicate = self.client.post(
            reverse("manage_supplier_list"),
            data=json.dumps({"name": "buildsupply ltd"}),
            content_type="application/json",
        )
        self.assertEqual(duplicate.status_code, 400)
        self.assertEqual(duplicate.json()["code"], "duplicate_supplier_name")

    def test_console_supplier_create_and_deactivate_write_audit_history(self):
        self.client.force_login(self.staff_user)

        create_response = self.client.post(
            reverse("manage_supplier_list"),
            data=json.dumps({"name": "BuildSupply Ltd"}),
            content_type="application/json",
        )
        supplier_id = create_response.json()["supplier"]["id"]

        self.client.patch(
            reverse("manage_supplier_detail", args=[supplier_id]),
            data=json.dumps({"is_active": False}),
            content_type="application/json",
        )

        history = self.client.get(
            reverse("manage_supplier_history", args=[supplier_id]),
        )
        self.assertEqual(history.status_code, 200)
        by_action = {entry["action"]: entry for entry in history.json()["history"]}
        self.assertEqual(set(by_action), {"created", "deactivated"})
        self.assertEqual(by_action["created"]["user_email"], self.staff_user.email)

    def test_non_staff_user_cannot_use_supplier_api(self):
        self.client.force_login(self.non_staff_user)

        response = self.client.get(reverse("manage_supplier_list"))

        self.assertEqual(response.status_code, 403)

    def test_operator_cannot_create_supplier(self):
        operator = make_warehouse_user(
            "operator-supplier@example.com",
            group_name=GROUP_OPERATORS,
        )
        self.client.force_login(operator)

        listing = self.client.get(reverse("manage_supplier_list"))
        self.assertEqual(listing.status_code, 200)

        created = self.client.post(
            reverse("manage_supplier_list"),
            data=json.dumps({"name": "Blocked Supplier"}),
            content_type="application/json",
        )
        self.assertEqual(created.status_code, 403)
        self.assertEqual(
            created.json()["error"],
            "Missing permission: products.add_supplier",
        )


class SeedDevDataCommandTests(TestCase):
    def test_seed_resolves_existing_family_when_case_differs(self):
        create_family("cement")

        call_command("seed_dev_data", verbosity=0)

        self.assertTrue(
            get_user_model().objects.filter(
                email="warehouse.admin@centcompras.dev",
            ).exists()
        )
        item = Item.objects.get(internal_code="CEM-50")
        self.assertEqual(item.family.name, "cement")
        self.assertEqual(
            FamilyProduct.objects.filter(name__iexact="Cement").count(),
            1,
        )


class BulkLifecycleAtomicityTests(ItemTestCaseMixin, TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            email="bulk@example.com",
            password="test-pass-123",
        )
        self.family = self.create_test_family()

    def test_bulk_deactivate_marks_all_inactive(self):
        first = self.create_test_item(self.user, description="First")
        second = self.create_test_item(self.user, description="Second")

        bulk_deactivate_items(self.user, [first, second], reason="End of line")

        first.refresh_from_db()
        second.refresh_from_db()
        self.assertFalse(first.is_active)
        self.assertFalse(second.is_active)
        self.assertEqual(
            first.change_logs.filter(action=ItemChangeLog.Action.DEACTIVATED).count(),
            1,
        )

    def test_bulk_deactivate_rolls_back_when_one_item_fails(self):
        first = self.create_test_item(self.user, description="First")
        second = self.create_test_item(self.user, description="Second")

        original_deactivate = deactivate_item
        calls = {"count": 0}

        def failing_deactivate(user, item, reason=""):
            calls["count"] += 1
            if calls["count"] == 2:
                raise RuntimeError("boom")
            return original_deactivate(user, item, reason=reason)

        with mock.patch(
            "products.services.deactivate_item",
            side_effect=failing_deactivate,
        ):
            with self.assertRaises(RuntimeError):
                bulk_deactivate_items(
                    self.user,
                    [first, second],
                    reason="End of line",
                )

        first.refresh_from_db()
        second.refresh_from_db()
        self.assertTrue(first.is_active)
        self.assertTrue(second.is_active)


class ServiceValidationTests(ItemTestCaseMixin, TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            email="validation@example.com",
            password="test-pass-123",
        )
        self.family = self.create_test_family()
        self.vat_rate = VatRate.objects.get(code="VAT16")

    def test_create_item_rejects_overlong_description(self):
        with self.assertRaises(ValidationError):
            create_item(
                self.user,
                family=self.family,
                description="x" * 256,
                unit_of_measure=Item.UnitOfMeasure.PIECE,
                vat_rate=self.vat_rate,
            )

    def test_create_item_rejects_overlong_internal_code(self):
        with self.assertRaises(ValidationError):
            create_item(
                self.user,
                family=self.family,
                description="OK",
                internal_code="C" * 65,
                unit_of_measure=Item.UnitOfMeasure.PIECE,
                vat_rate=self.vat_rate,
            )

    def test_create_item_rejects_reorder_level_overflow(self):
        with self.assertRaises(ValidationError):
            create_item(
                self.user,
                family=self.family,
                description="OK",
                reorder_level="12345678901.123",
                unit_of_measure=Item.UnitOfMeasure.PIECE,
                vat_rate=self.vat_rate,
            )

    def test_create_family_rejects_overlong_name(self):
        with self.assertRaises(ValidationError):
            create_family(name="F" * 256)

    def test_create_supplier_rejects_overlong_name(self):
        with self.assertRaises(ValidationError):
            create_supplier(name="S" * 256)


class SaveHelperDuplicateMappingTests(TestCase):
    def setUp(self):
        self.family = create_family("Dup Family")
        self.vat_rate = VatRate.objects.get(code="VAT16")

    def test_save_item_maps_db_unique_violation(self):
        Item.objects.create(
            family=self.family,
            description="Existing",
            unit_of_measure=Item.UnitOfMeasure.PIECE,
            vat_rate=self.vat_rate,
            internal_code="CODE-1",
        )
        dup = Item(
            family=self.family,
            description="Another",
            unit_of_measure=Item.UnitOfMeasure.PIECE,
            vat_rate=self.vat_rate,
            internal_code="CODE-1",
        )
        with self.assertRaises(DuplicateInternalCodeError):
            _save_item(dup)

    def test_save_family_maps_db_unique_violation(self):
        create_family("Unique Family")
        dup = FamilyProduct(name="unique family")
        with self.assertRaises(DuplicateFamilyNameError):
            _save_family(dup)

    def test_save_supplier_maps_db_unique_violation(self):
        create_supplier("Dup Supplier")
        dup = Supplier(name="DUP SUPPLIER")
        with self.assertRaises(DuplicateSupplierNameError):
            _save_supplier(dup)


class SellingPriceServiceTests(ItemTestCaseMixin, TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            email="staff@example.com",
            password="test-pass-123",
        )
        self.family = self.create_test_family()
        self.vat_rate = VatRate.objects.get(code="VAT16")

    def test_create_item_stores_selling_prices(self):
        item = create_item(
            self.user,
            family=self.family,
            description="Priced item",
            unit_of_measure=Item.UnitOfMeasure.PIECE,
            vat_rate=self.vat_rate,
            retail_price="99.99",
            wholesale_price="75.00",
            special_price="60.00",
        )

        self.assertEqual(item.retail_price, Decimal("99.99"))
        self.assertEqual(item.wholesale_price, Decimal("75.00"))
        self.assertEqual(item.special_price, Decimal("60.00"))
        log = item.change_logs.get(action=ItemChangeLog.Action.CREATED)
        self.assertEqual(log.changes["retail_price"], "99.99")
        self.assertEqual(log.changes["wholesale_price"], "75.00")
        self.assertEqual(log.changes["special_price"], "60.00")

    def test_update_item_selling_prices_writes_audit_diff(self):
        item = self.create_test_item(self.user, description="Priced item")

        update_item(
            self.user,
            item,
            retail_price="10.00",
            wholesale_price="8.00",
            special_price="6.50",
        )

        log = item.change_logs.get(action=ItemChangeLog.Action.UPDATED)
        self.assertEqual(log.changes["retail_price"]["new"], "10.00")
        self.assertEqual(log.changes["wholesale_price"]["new"], "8.00")
        self.assertEqual(log.changes["special_price"]["new"], "6.50")


class SupplierItemPriceServiceTests(ItemTestCaseMixin, TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            email="staff@example.com",
            password="test-pass-123",
        )
        self.family = self.create_test_family()
        self.vat_rate = VatRate.objects.get(code="VAT16")
        self.item = self.create_test_item(
            self.user,
            description="Cement 50kg",
            internal_code="CEM-50",
        )
        self.supplier = create_supplier(name="BuildSupply Ltd")

    def test_create_supplier_item_price_writes_audit_log(self):
        sip = create_supplier_item_price(
            supplier=self.supplier,
            item=self.item,
            cost_price="12.50",
            primary=True,
            user=self.user,
        )

        log = sip.change_logs.get(action=SupplierItemPriceChangeLog.Action.CREATED)
        self.assertEqual(log.user, self.user)
        self.assertEqual(log.changes["cost_price"], "12.50")
        self.assertTrue(log.changes["primary"])
        self.assertEqual(log.changes["supplier"]["name"], self.supplier.name)
        self.assertEqual(log.changes["item"]["internal_code"], "CEM-50")

    def test_duplicate_supplier_item_price_is_rejected(self):
        create_supplier_item_price(self.supplier, self.item, "12.50")

        with self.assertRaises(DuplicateSupplierItemPriceError):
            create_supplier_item_price(self.supplier, self.item, "9.99")

        self.assertEqual(SupplierItemPrice.objects.count(), 1)

    def test_negative_cost_price_is_rejected(self):
        with self.assertRaises(InvalidCostPriceError):
            create_supplier_item_price(self.supplier, self.item, "-1")

    def test_update_supplier_item_price_writes_audit_and_diff(self):
        sip = create_supplier_item_price(self.supplier, self.item, "12.50")

        update_supplier_item_price(sip, user=self.user, cost_price="13.75")

        sip.refresh_from_db()
        self.assertEqual(sip.cost_price, Decimal("13.75"))
        log = sip.change_logs.get(action=SupplierItemPriceChangeLog.Action.UPDATED)
        self.assertEqual(log.user, self.user)
        self.assertEqual(log.changes["cost_price"]["old"], "12.50")
        self.assertEqual(log.changes["cost_price"]["new"], "13.75")

    def test_setting_primary_clears_other_primaries(self):
        other_supplier = create_supplier(name="Porto Materials Co")
        first = create_supplier_item_price(
            self.supplier, self.item, "12.50", primary=True, user=self.user
        )
        first_updated_at = first.updated_at
        second = create_supplier_item_price(
            other_supplier, self.item, "11.00", primary=True, user=self.user
        )

        first.refresh_from_db()
        second.refresh_from_db()
        self.assertTrue(second.primary)
        self.assertFalse(first.primary)
        self.assertGreater(first.updated_at, first_updated_at)

        demote_log = first.change_logs.get(
            action=SupplierItemPriceChangeLog.Action.UPDATED
        )
        self.assertEqual(demote_log.user, self.user)
        self.assertEqual(demote_log.changes["primary"]["old"], True)
        self.assertEqual(demote_log.changes["primary"]["new"], False)

    def test_update_primary_audits_cleared_primaries(self):
        other_supplier = create_supplier(name="Porto Materials Co")
        first = create_supplier_item_price(
            self.supplier, self.item, "12.50", primary=True, user=self.user
        )
        second = create_supplier_item_price(
            other_supplier, self.item, "11.00", primary=False, user=self.user
        )
        first_updated_at = first.updated_at

        update_supplier_item_price(second, user=self.user, primary=True)

        first.refresh_from_db()
        second.refresh_from_db()
        self.assertTrue(second.primary)
        self.assertFalse(first.primary)
        self.assertGreater(first.updated_at, first_updated_at)

        demote_log = first.change_logs.get(
            action=SupplierItemPriceChangeLog.Action.UPDATED
        )
        self.assertEqual(demote_log.user, self.user)
        self.assertEqual(demote_log.changes["primary"]["old"], True)
        self.assertEqual(demote_log.changes["primary"]["new"], False)

    def test_get_item_buying_price_prefers_primary_then_cheapest(self):
        other_supplier = create_supplier(name="Porto Materials Co")
        create_supplier_item_price(self.supplier, self.item, "12.50", primary=False)
        create_supplier_item_price(other_supplier, self.item, "9.99", primary=False)

        self.assertEqual(get_item_buying_price(self.item), Decimal("9.99"))

        primary_sip = SupplierItemPrice.objects.get(
            supplier=self.supplier, item=self.item
        )
        update_supplier_item_price(primary_sip, primary=True)
        self.assertEqual(get_item_buying_price(self.item), Decimal("12.50"))

    def test_get_item_buying_price_returns_none_without_prices(self):
        self.assertIsNone(get_item_buying_price(self.item))

    def test_nan_cost_price_is_rejected(self):
        with self.assertRaises(InvalidCostPriceError):
            create_supplier_item_price(self.supplier, self.item, "NaN")

    def test_get_supplier_item_price_history_newest_first(self):
        sip = create_supplier_item_price(self.supplier, self.item, "12.50")
        update_supplier_item_price(sip, cost_price="13.75")

        actions = list(
            get_supplier_item_price_history(sip).values_list("action", flat=True)
        )
        self.assertEqual(
            actions,
            [
                SupplierItemPriceChangeLog.Action.UPDATED,
                SupplierItemPriceChangeLog.Action.CREATED,
            ],
        )

    def test_db_rejects_two_primary_prices_for_same_item(self):
        from django.db import IntegrityError

        create_supplier_item_price(
            self.supplier, self.item, "12.50", primary=True, user=self.user
        )
        other = create_supplier(name="Porto Materials Co")
        second = create_supplier_item_price(
            other, self.item, "11.00", primary=False, user=self.user
        )
        with self.assertRaises(IntegrityError):
            SupplierItemPrice.objects.filter(pk=second.pk).update(primary=True)

    def test_create_primary_locks_item_for_update(self):
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        with CaptureQueriesContext(connection) as ctx:
            create_supplier_item_price(
                self.supplier, self.item, "12.50", primary=True, user=self.user
            )
        for_update = [
            query["sql"]
            for query in ctx.captured_queries
            if "FOR UPDATE" in query["sql"] and "products_item" in query["sql"].lower()
        ]
        self.assertGreaterEqual(len(for_update), 1)


class SupplierItemPricePermissionTests(TestCase):
    def test_operator_has_view_only_permission(self):
        operator = make_warehouse_user("op-sip@example.com", group_name=GROUP_OPERATORS)
        self.assertTrue(operator.has_perm("products.view_supplieritemprice"))
        self.assertFalse(operator.has_perm("products.add_supplieritemprice"))
        self.assertFalse(operator.has_perm("products.change_supplieritemprice"))

    def test_manager_can_add_and_change_but_not_delete(self):
        manager = make_warehouse_user("mgr-sip@example.com", group_name=GROUP_MANAGERS)
        self.assertTrue(manager.has_perm("products.add_supplieritemprice"))
        self.assertTrue(manager.has_perm("products.change_supplieritemprice"))
        self.assertFalse(manager.has_perm("products.delete_supplieritemprice"))

    def test_admin_can_delete(self):
        admin = make_warehouse_user("adm-sip@example.com", group_name=GROUP_ADMINS)
        self.assertTrue(admin.has_perm("products.delete_supplieritemprice"))


class SupplierItemPriceAdminAccessTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.superuser = user_model.objects.create_superuser(
            email="super@example.com",
            password="test-pass-123",
        )
        self.warehouse_user = make_warehouse_user("warehouse@example.com")
        self.client = Client()
        self.sip_changelist_url = reverse(
            "admin:products_supplieritemprice_changelist"
        )

    def test_superuser_can_open_supplier_item_price_admin(self):
        self.client.force_login(self.superuser)
        response = self.client.get(self.sip_changelist_url)
        self.assertEqual(response.status_code, 200)

    def test_warehouse_user_cannot_open_supplier_item_price_admin(self):
        self.client.force_login(self.warehouse_user)
        response = self.client.get(self.sip_changelist_url)
        self.assertIn(response.status_code, (302, 403))


class SupplierItemPriceConsoleTests(ItemTestCaseMixin, TestCase):
    def setUp(self):
        self.staff_user = make_warehouse_user("warehouse@example.com")
        self.non_staff_user = get_user_model().objects.create_user(
            email="user@example.com",
            password="test-pass-123",
        )
        self.client = Client()
        self.family = self.create_test_family()
        self.vat_rate = VatRate.objects.get(code="VAT16")
        self.item = self.create_test_item(
            self.staff_user,
            description="Cement 50kg",
            internal_code="CEM-50",
        )
        self.supplier = create_supplier(name="BuildSupply Ltd")

    def test_staff_can_create_and_update_supplier_item_price_through_api(self):
        self.client.force_login(self.staff_user)

        create_response = self.client.post(
            reverse("manage_supplier_item_price_list"),
            data=json.dumps({
                "supplier_id": self.supplier.id,
                "item_id": self.item.id,
                "cost_price": "12.50",
                "primary": True,
            }),
            content_type="application/json",
        )
        self.assertEqual(create_response.status_code, 200)
        sip = create_response.json()["supplier_item_price"]
        self.assertEqual(sip["cost_price"], "12.50")
        self.assertTrue(sip["primary"])
        self.assertEqual(sip["supplier_name"], "BuildSupply Ltd")
        self.assertEqual(sip["internal_code"], "CEM-50")

        update_response = self.client.patch(
            reverse("manage_supplier_item_price_detail", args=[sip["id"]]),
            data=json.dumps({"cost_price": "13.75"}),
            content_type="application/json",
        )
        self.assertEqual(update_response.status_code, 200)
        self.assertEqual(
            update_response.json()["supplier_item_price"]["cost_price"],
            "13.75",
        )

        list_response = self.client.get(
            reverse("manage_supplier_item_price_list"),
            {"item_id": self.item.id},
        )
        rows = list_response.json()["supplier_item_prices"]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["cost_price"], "13.75")

    def test_console_rejects_duplicate_and_negative(self):
        self.client.force_login(self.staff_user)
        create_supplier_item_price(self.supplier, self.item, "12.50")

        duplicate = self.client.post(
            reverse("manage_supplier_item_price_list"),
            data=json.dumps({
                "supplier_id": self.supplier.id,
                "item_id": self.item.id,
                "cost_price": "9.99",
            }),
            content_type="application/json",
        )
        self.assertEqual(duplicate.status_code, 400)
        self.assertEqual(duplicate.json()["code"], "duplicate_supplier_item_price")

        negative = self.client.post(
            reverse("manage_supplier_item_price_list"),
            data=json.dumps({
                "supplier_id": self.supplier.id,
                "item_id": self.item.id,
                "cost_price": "-1",
            }),
            content_type="application/json",
        )
        self.assertEqual(negative.status_code, 400)
        self.assertEqual(negative.json()["code"], "invalid_cost_price")

    def test_operator_cannot_create_supplier_item_price(self):
        operator = make_warehouse_user("op-sip@example.com", group_name=GROUP_OPERATORS)
        self.client.force_login(operator)

        response = self.client.post(
            reverse("manage_supplier_item_price_list"),
            data=json.dumps({
                "supplier_id": self.supplier.id,
                "item_id": self.item.id,
                "cost_price": "12.50",
            }),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 403)

    def test_non_staff_cannot_use_supplier_item_price_api(self):
        self.client.force_login(self.non_staff_user)
        response = self.client.get(reverse("manage_supplier_item_price_list"))
        self.assertEqual(response.status_code, 403)

    def test_staff_can_create_item_with_selling_prices_through_api(self):
        self.client.force_login(self.staff_user)

        response = self.client.post(
            reverse("manage_item_list"),
            data=json.dumps({
                "family_id": self.family.id,
                "description": "Priced item",
                "unit_of_measure": "piece",
                "vat_rate_id": self.vat_rate.id,
                "retail_price": "99.99",
                "wholesale_price": "75.00",
                "special_price": "60.00",
            }),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        item = response.json()["item"]
        self.assertEqual(item["retail_price"], "99.99")
        self.assertEqual(item["wholesale_price"], "75.00")
        self.assertEqual(item["special_price"], "60.00")


class CatalogServiceTests(ItemTestCaseMixin, TestCase):
    def setUp(self):
        self.user = make_warehouse_user("catalog@example.com")
        self.family = self.create_test_family()
        self.vat_rate = VatRate.objects.get(code="VAT16")
        self.item = self.create_test_item(
            self.user,
            description="Cement 50kg",
            internal_code="CEM-50",
            reorder_level="10",
        )
        self.supplier = create_supplier(name="BuildSupply Ltd")

    def test_get_catalog_returns_active_items(self):
        create_supplier_item_price(
            self.supplier, self.item, "8.50", primary=True, user=self.user
        )
        items = list(get_catalog())
        self.assertEqual([item.pk for item in items], [self.item.pk])

    def test_catalog_buying_price_prefers_primary_then_cheapest(self):
        other = create_supplier(name="Porto Materials Co")
        create_supplier_item_price(self.supplier, self.item, "12.50", primary=False)
        create_supplier_item_price(other, self.item, "9.99", primary=False)

        item = get_catalog().get(pk=self.item.pk)
        self.assertEqual(catalog_buying_price(item), Decimal("9.99"))

        primary = SupplierItemPrice.objects.get(supplier=self.supplier, item=self.item)
        update_supplier_item_price(primary, primary=True)
        item = get_catalog().get(pk=self.item.pk)
        self.assertEqual(catalog_buying_price(item), Decimal("12.50"))

    def test_catalog_buying_price_none_without_prices(self):
        item = get_catalog().get(pk=self.item.pk)
        self.assertIsNone(catalog_buying_price(item))

    def test_catalog_below_reorder_flags_at_or_below(self):
        item = get_catalog().get(pk=self.item.pk)
        self.assertTrue(catalog_below_reorder(item))
        item.quantity = Decimal("10")
        self.assertTrue(catalog_below_reorder(item))
        item.quantity = Decimal("11")
        self.assertFalse(catalog_below_reorder(item))

    def test_catalog_below_reorder_ignores_zero_reorder_level(self):
        item = get_catalog().get(pk=self.item.pk)
        item.reorder_level = Decimal("0")
        item.quantity = Decimal("0")
        self.assertFalse(catalog_below_reorder(item))

    def test_catalog_buying_price_ignores_deactivated_supplier(self):
        other = create_supplier(name="Porto Materials Co")
        create_supplier_item_price(self.supplier, self.item, "12.50", primary=True)
        create_supplier_item_price(other, self.item, "9.99", primary=False)

        self.supplier.is_active = False
        self.supplier.save()

        item = get_catalog().get(pk=self.item.pk)
        self.assertEqual(catalog_buying_price(item), Decimal("9.99"))


class CatalogConsoleTests(ItemTestCaseMixin, TestCase):
    def setUp(self):
        self.staff_user = make_warehouse_user("catalog-console@example.com")
        self.non_staff_user = get_user_model().objects.create_user(
            email="plain@example.com", password="test-pass-123"
        )
        self.client = Client()
        self.family = self.create_test_family()
        self.vat_rate = VatRate.objects.get(code="VAT16")
        self.item = self.create_test_item(
            self.staff_user,
            description="Cement 50kg",
            internal_code="CEM-50",
            reorder_level="10",
        )
        self.supplier = create_supplier(name="BuildSupply Ltd")
        create_supplier_item_price(
            self.supplier, self.item, "8.50", primary=True, user=self.staff_user
        )

    def test_staff_can_open_catalog_console(self):
        self.client.force_login(self.staff_user)
        response = self.client.get(reverse("catalog_console"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "catalog-body")

    def test_catalog_api_returns_joined_data(self):
        self.client.force_login(self.staff_user)
        response = self.client.get(reverse("manage_catalog_list"))
        self.assertEqual(response.status_code, 200)
        catalog = response.json()["catalog"]
        self.assertEqual(len(catalog), 1)
        row = catalog[0]
        self.assertEqual(row["internal_code"], "CEM-50")
        self.assertEqual(row["family"]["name"], self.family.name)
        self.assertEqual(Decimal(row["quantity"]), Decimal("0"))
        self.assertEqual(Decimal(row["reorder_level"]), Decimal("10"))
        self.assertEqual(Decimal(row["buying_price"]), Decimal("8.50"))
        self.assertTrue(row["below_reorder"])
        self.assertEqual(row["suppliers"][0]["name"], self.supplier.name)
        self.assertTrue(row["suppliers"][0]["primary"])

    def test_catalog_api_requires_view_permission(self):
        self.client.force_login(self.non_staff_user)
        response = self.client.get(reverse("manage_catalog_list"))
        self.assertEqual(response.status_code, 403)

    def test_catalog_api_requires_login(self):
        response = self.client.get(reverse("manage_catalog_list"))
        self.assertEqual(response.status_code, 401)

    def test_catalog_api_rejects_bad_family_id(self):
        self.client.force_login(self.staff_user)
        response = self.client.get(reverse("manage_catalog_list") + "?family_id=abc")
        self.assertEqual(response.status_code, 400)
