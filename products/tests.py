import json
import re
import subprocess
import uuid
from decimal import Decimal
from unittest import mock

from django.contrib.auth import get_user_model
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.core.management.base import CommandError
from django.contrib.admin.helpers import ACTION_CHECKBOX_NAME
from django.contrib.messages import get_messages
from django.test import Client, SimpleTestCase, TestCase
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
    SubFamily,
    SubFamilyChangeLog,
    Supplier,
    SupplierChangeLog,
    SupplierItemPrice,
    SupplierItemPriceChangeLog,
    VatRate,
)
from products.permissions import can_view_catalog
from products.services import (
    DeactivateReasonRequiredError,
    CostPriceGenesisRequiredError,
    DescriptionRequiredError,
    DuplicateFamilyNameError,
    DuplicateInternalCodeError,
    DuplicateSubFamilyNameError,
    DuplicateSupplierItemPriceError,
    DuplicateSupplierNameError,
    FamilyNameRequiredError,
    InactiveFamilyError,
    InactiveItemError,
    InactiveSubFamilyError,
    InactiveSupplierError,
    InvalidCostPriceError,
    InvalidInternalCodeError,
    InternalCodeImmutableError,
    ItemGenesisNotReadyError,
    InvalidReorderLevelError,
    InvalidSellingPriceError,
    InvalidSupplierEmailError,
    ReactivateReasonRequiredError,
    SupplierNameRequiredError,
    SubFamilyFamilyMismatchError,
    SubFamilyNameRequiredError,
    _save_family,
    _save_item,
    _save_supplier,
    bulk_deactivate_items,
    bulk_reactivate_items,
    build_item_primary_cost_timeline,
    catalog_below_reorder,
    catalog_buying_price,
    create_family,
    create_and_activate_item,
    create_item,
    create_sub_family,
    create_supplier,
    create_supplier_item_price,
    deactivate_item,
    get_catalog,
    get_families,
    get_item_buying_price,
    get_item_primary_cost_series,
    get_items,
    get_sub_families,
    get_sub_family_history,
    get_supplier_history,
    get_supplier_item_price_history,
    get_supplier_item_prices,
    get_suppliers,
    reactivate_item,
    resolve_cost_trend_window,
    update_family,
    update_item,
    update_sub_family,
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

    def create_test_supplier(self, name=None):
        if name is None:
            name = f"Test Supplier {uuid.uuid4().hex[:8]}"
        return create_supplier(name=name)

    def create_test_item(self, user, family=None, active=True, **kwargs):
        if family is None:
            family = self.family
        if "vat_rate" not in kwargs:
            kwargs["vat_rate"] = VatRate.objects.get(code="VAT16")
        with_primary_supplier = kwargs.pop("with_primary_supplier", True)
        defaults = {
            "family": family,
            "description": "Test item",
            "unit_of_measure": Item.UnitOfMeasure.PIECE,
        }
        defaults.update(kwargs)
        if not defaults.get("internal_code"):
            defaults["internal_code"] = f"T-{uuid.uuid4().hex[:8].upper()}"
        if "retail_price" not in defaults:
            defaults["retail_price"] = "1.00"
        if active:
            if with_primary_supplier:
                supplier = defaults.pop("supplier", None)
                cost_price = defaults.pop("cost_price", "5.00")
                if supplier is None:
                    supplier = getattr(self, "supplier", None) or self.create_test_supplier()
                item = create_and_activate_item(
                    user,
                    supplier=supplier,
                    cost_price=cost_price,
                    **defaults,
                )
                item.refresh_from_db()
                return item
            item = create_item(user, **defaults)
            reactivate_item(user, item, reason="Genesis")
            item.refresh_from_db()
            return item
        defaults.pop("supplier", None)
        defaults.pop("cost_price", None)
        item = create_item(user, **defaults)
        return item

    def genesis_create_payload(self, **overrides):
        supplier = getattr(self, "supplier", None) or self.create_test_supplier()
        family = getattr(self, "family", None) or self.create_test_family()
        vat_rate = getattr(self, "vat_rate", None) or VatRate.objects.get(code="VAT16")
        payload = {
            "family_id": family.id,
            "description": "Genesis item",
            "unit_of_measure": Item.UnitOfMeasure.PIECE,
            "internal_code": "GEN-API-1",
            "retail_price": "10.00",
            "vat_rate_id": vat_rate.id,
            "supplier_id": supplier.id,
            "cost_price": "5.00",
        }
        payload.update(overrides)
        return payload


class ItemServiceTests(ItemTestCaseMixin, TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            email="staff@example.com",
            password="test-pass-123",
        )
        self.family = self.create_test_family()
        self.vat_rate = VatRate.objects.get(code="VAT16")
        self.supplier = self.create_test_supplier()

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

    def test_internal_code_format_rejects_spaces_and_symbols(self):
        for internal_code in ("ABC DEF", "CEM@50", "code#1"):
            with self.subTest(internal_code=internal_code):
                with self.assertRaises(InvalidInternalCodeError):
                    validate_internal_code_available(internal_code)

                with self.assertRaises(InvalidInternalCodeError):
                    create_item(
                        self.user,
                        family=self.family,
                        description="Invalid code item",
                        internal_code=internal_code,
                        unit_of_measure=Item.UnitOfMeasure.PIECE,
                        vat_rate=self.vat_rate,
                    )

    def test_internal_code_format_accepts_valid_codes(self):
        for internal_code in ("", "CEM-50", "CEM_50", "abc123", "CABLE-2.5", "PIPE.20"):
            with self.subTest(internal_code=internal_code):
                item = create_item(
                    self.user,
                    family=self.family,
                    description=f"Item {internal_code or 'no-code'}",
                    internal_code=internal_code,
                    unit_of_measure=Item.UnitOfMeasure.PIECE,
                    vat_rate=self.vat_rate,
                )
                self.assertEqual(
                    item.internal_code,
                    internal_code.upper() if internal_code else "",
                )

    def test_internal_code_is_stored_uppercase(self):
        item = create_item(
            self.user,
            family=self.family,
            description="Lowercase typed code",
            internal_code="cem-50",
            unit_of_measure=Item.UnitOfMeasure.PIECE,
            vat_rate=self.vat_rate,
        )
        self.assertEqual(item.internal_code, "CEM-50")

        update_item(self.user, item, internal_code="cem-50")
        item.refresh_from_db()
        self.assertEqual(item.internal_code, "CEM-50")

    def test_update_item_rejects_invalid_internal_code_format(self):
        item = create_item(
            self.user,
            family=self.family,
            description="Existing",
            internal_code="",
            unit_of_measure=Item.UnitOfMeasure.PIECE,
            vat_rate=self.vat_rate,
        )

        with self.assertRaises(InvalidInternalCodeError):
            update_item(self.user, item, internal_code="BAD CODE")

    def test_update_item_rejects_duplicate_internal_code(self):
        self.create_test_item(
            self.user,
            description="First",
            internal_code="CODE-A",
        )
        second = create_item(
            self.user,
            family=self.family,
            description="Second",
            internal_code="",
            unit_of_measure=Item.UnitOfMeasure.PIECE,
            vat_rate=self.vat_rate,
        )

        with self.assertRaises(DuplicateInternalCodeError):
            update_item(
                self.user,
                second,
                internal_code="CODE-A",
            )

    def test_update_item_rejects_internal_code_change(self):
        item = self.create_test_item(
            self.user,
            description="Locked code",
            internal_code="LOCK-1",
        )

        with self.assertRaises(InternalCodeImmutableError):
            update_item(self.user, item, internal_code="LOCK-2")

    def test_update_item_allows_set_if_empty_internal_code_once(self):
        item = create_item(
            self.user,
            family=self.family,
            description="Legacy inactive",
            unit_of_measure=Item.UnitOfMeasure.PIECE,
            vat_rate=self.vat_rate,
            internal_code="",
        )

        update_item(self.user, item, internal_code="legacy-1")
        item.refresh_from_db()
        self.assertEqual(item.internal_code, "LEGACY-1")

        with self.assertRaises(InternalCodeImmutableError):
            update_item(self.user, item, internal_code="LEGACY-2")

    def test_reactivate_first_activation_requires_genesis_fields(self):
        item = create_item(
            self.user,
            family=self.family,
            description="Incomplete",
            unit_of_measure=Item.UnitOfMeasure.PIECE,
            vat_rate=self.vat_rate,
            internal_code="",
            retail_price="0",
        )

        with self.assertRaises(ItemGenesisNotReadyError):
            reactivate_item(self.user, item, reason="Genesis")

    def test_reactivate_after_deactivate_skips_genesis_qualification(self):
        item = self.create_test_item(
            self.user,
            description="Was active",
            internal_code="WAS-1",
            retail_price=Decimal("1.00"),
        )
        deactivate_item(self.user, item, reason="Temporarily unavailable")
        item.retail_price = Decimal("0")
        item.save(update_fields=["retail_price"])

        reactivate_item(self.user, item, reason="Back in stock")
        item.refresh_from_db()
        self.assertTrue(item.is_active)

    def test_create_and_activate_item_returns_active(self):
        item = create_and_activate_item(
            self.user,
            family=self.family,
            description="Genesis item",
            unit_of_measure=Item.UnitOfMeasure.PIECE,
            vat_rate=self.vat_rate,
            supplier=self.supplier,
            cost_price="8.50",
            internal_code="GEN-1",
            retail_price="12.50",
        )

        self.assertTrue(item.is_active)
        self.assertEqual(
            item.change_logs.filter(action=ItemChangeLog.Action.REACTIVATED).count(),
            1,
        )
        primary = SupplierItemPrice.objects.get(item=item, primary=True)
        self.assertEqual(primary.supplier_id, self.supplier.pk)
        self.assertEqual(primary.cost_price, Decimal("8.50"))

    def test_create_and_activate_item_rolls_back_on_genesis_failure(self):
        with self.assertRaises(ItemGenesisNotReadyError):
            create_and_activate_item(
                self.user,
                family=self.family,
                description="No retail",
                unit_of_measure=Item.UnitOfMeasure.PIECE,
                vat_rate=self.vat_rate,
                supplier=self.supplier,
                cost_price="5.00",
                internal_code="GEN-2",
                retail_price="0",
            )

        self.assertFalse(Item.objects.filter(internal_code="GEN-2").exists())

    def test_create_and_activate_item_requires_positive_cost(self):
        with self.assertRaises(CostPriceGenesisRequiredError):
            create_and_activate_item(
                self.user,
                family=self.family,
                description="No cost",
                unit_of_measure=Item.UnitOfMeasure.PIECE,
                vat_rate=self.vat_rate,
                supplier=self.supplier,
                cost_price="0",
                internal_code="GEN-4",
                retail_price="12.50",
            )

        self.assertFalse(Item.objects.filter(internal_code="GEN-4").exists())

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

    def test_reactivate_item_rejects_inactive_family(self):
        item = create_item(
            self.user,
            family=self.family,
            description="Under inactive family",
            unit_of_measure=Item.UnitOfMeasure.PIECE,
            vat_rate=self.vat_rate,
        )
        update_family(self.family, is_active=False)

        with self.assertRaises(InactiveFamilyError):
            reactivate_item(self.user, item, reason="Back in stock")

        item.refresh_from_db()
        self.assertFalse(item.is_active)

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

    def test_update_family_rejects_name_change(self):
        family = create_family("Original")

        with self.assertRaises(ValueError):
            update_family(family, name="Renamed")

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

    def test_update_family_toggles_is_active(self):
        family = create_family("Cement")

        updated = update_family(family, is_active=False)

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

        update_family(family, is_active=True)

        self.assertEqual(family.change_logs.count(), 1)
        self.assertEqual(
            family.change_logs.get().action,
            FamilyChangeLog.Action.CREATED,
        )


class SubFamilyServiceTests(TestCase):
    def setUp(self):
        self.family = create_family("Cement")
        self.other_family = create_family("Pipes")

    def test_create_sub_family_rejects_empty_name(self):
        with self.assertRaises(SubFamilyNameRequiredError):
            create_sub_family("   ", self.family)

        self.assertEqual(SubFamily.objects.count(), 0)

    def test_create_sub_family_rejects_duplicate_name_in_same_family(self):
        create_sub_family("Bags", self.family)

        with self.assertRaises(DuplicateSubFamilyNameError):
            create_sub_family("bags", self.family)

        self.assertEqual(SubFamily.objects.filter(family=self.family).count(), 1)

    def test_same_sub_family_name_allowed_under_different_families(self):
        create_sub_family("Steel", self.family)
        other = create_sub_family("Steel", self.other_family)

        self.assertEqual(other.family_id, self.other_family.pk)

    def test_create_sub_family_rejects_inactive_parent_family(self):
        inactive = create_family("Inactive", is_active=False)

        with self.assertRaises(InactiveFamilyError):
            create_sub_family("Bags", inactive)

    def test_update_sub_family_rejects_name_and_parent_change(self):
        sub_family = create_sub_family("Bags", self.family)

        with self.assertRaises(ValueError):
            update_sub_family(sub_family, name="Bulk")

        with self.assertRaises(ValueError):
            update_sub_family(sub_family, family=self.other_family)

        sub_family.refresh_from_db()
        self.assertEqual(sub_family.name, "Bags")
        self.assertEqual(sub_family.family_id, self.family.pk)

    def test_update_sub_family_toggles_is_active(self):
        sub_family = create_sub_family("Bags", self.family)

        updated = update_sub_family(sub_family, is_active=False)

        self.assertFalse(updated.is_active)

    def test_create_sub_family_writes_audit_log(self):
        user_model = get_user_model()
        user = user_model.objects.create_user(
            email="sub-family@example.com",
            password="test-pass-123",
        )

        sub_family = create_sub_family("Bags", self.family, user=user)

        log = sub_family.change_logs.get(action=SubFamilyChangeLog.Action.CREATED)
        self.assertEqual(log.user, user)
        self.assertEqual(log.changes["name"], "Bags")

    def test_item_optional_sub_family_on_create_and_genesis(self):
        user_model = get_user_model()
        user = user_model.objects.create_user(
            email="item-sub@example.com",
            password="test-pass-123",
        )
        sub_family = create_sub_family("Bags", self.family)
        vat_rate = VatRate.objects.get(code="VAT16")

        without = create_item(
            user,
            family=self.family,
            description="Plain cement",
            unit_of_measure=Item.UnitOfMeasure.KG,
            vat_rate=vat_rate,
            internal_code="CEM-PLAIN",
            retail_price="10.00",
        )
        self.assertIsNone(without.sub_family_id)

        with_sub = create_and_activate_item(
            user,
            family=self.family,
            description="Bagged cement",
            unit_of_measure=Item.UnitOfMeasure.KG,
            vat_rate=vat_rate,
            supplier=create_supplier(name="SubFamily Supplier"),
            cost_price="6.00",
            internal_code="CEM-BAG",
            retail_price="12.00",
            sub_family=sub_family,
        )
        self.assertEqual(with_sub.sub_family_id, sub_family.pk)

    def test_item_rejects_sub_family_family_mismatch(self):
        user_model = get_user_model()
        user = user_model.objects.create_user(
            email="mismatch@example.com",
            password="test-pass-123",
        )
        sub_family = create_sub_family("Steel", self.other_family)
        vat_rate = VatRate.objects.get(code="VAT16")

        with self.assertRaises(SubFamilyFamilyMismatchError):
            create_item(
                user,
                family=self.family,
                description="Mismatch",
                unit_of_measure=Item.UnitOfMeasure.M,
                vat_rate=vat_rate,
                internal_code="MISMATCH-1",
                retail_price="1.00",
                sub_family=sub_family,
            )

    def test_item_rejects_inactive_sub_family(self):
        user_model = get_user_model()
        user = user_model.objects.create_user(
            email="inactive-sub@example.com",
            password="test-pass-123",
        )
        sub_family = create_sub_family("Bags", self.family, is_active=False)
        vat_rate = VatRate.objects.get(code="VAT16")

        with self.assertRaises(InactiveSubFamilyError):
            create_item(
                user,
                family=self.family,
                description="Inactive sub",
                unit_of_measure=Item.UnitOfMeasure.KG,
                vat_rate=vat_rate,
                internal_code="INACT-SUB",
                retail_price="1.00",
                sub_family=sub_family,
            )

    def test_deactivate_sub_family_does_not_deactivate_items(self):
        user_model = get_user_model()
        user = user_model.objects.create_user(
            email="deact-sub@example.com",
            password="test-pass-123",
        )
        sub_family = create_sub_family("Bags", self.family)
        vat_rate = VatRate.objects.get(code="VAT16")
        supplier = create_supplier(name="Bag Supplier")
        item = create_and_activate_item(
            user,
            family=self.family,
            description="Bagged",
            unit_of_measure=Item.UnitOfMeasure.KG,
            vat_rate=vat_rate,
            supplier=supplier,
            cost_price="4.00",
            internal_code="BAG-1",
            retail_price="5.00",
            sub_family=sub_family,
        )

        update_sub_family(sub_family, is_active=False)

        item.refresh_from_db()
        self.assertTrue(item.is_active)
        self.assertEqual(item.sub_family_id, sub_family.pk)
        self.assertEqual(get_catalog().filter(pk=item.pk).count(), 1)


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

    def test_admin_create_rejects_inactive_family(self):
        inactive = create_family("Legacy", is_active=False)
        vat = VatRate.objects.get(code="VAT16")
        self.client.force_login(self.superuser)

        response = self.client.post(
            reverse("admin:products_item_add"),
            {
                "family": str(inactive.pk),
                "internal_code": "",
                "description": "Under inactive family",
                "unit_of_measure": "piece",
                "reorder_level": "0",
                "retail_price": "0",
                "wholesale_price": "0",
                "special_price": "0",
                "vat_rate": str(vat.pk),
                "_save": "Save",
            },
        )

        self.assertEqual(response.status_code, 200)
        form = response.context["adminform"].form
        self.assertFormError(
            form,
            "family",
            "Cannot assign items to inactive family 'Legacy'.",
        )

    def test_admin_reactivate_genesis_not_ready_shows_error(self):
        family = create_family("Reactivate family")
        vat = VatRate.objects.get(code="VAT16")
        item = create_item(
            user=self.superuser,
            family=family,
            internal_code="ADMIN-INCOMPLETE",
            description="Needs genesis",
            unit_of_measure="piece",
            vat_rate=vat,
            retail_price="0",
        )
        self.assertFalse(item.is_active)
        self.client.force_login(self.superuser)

        response = self.client.post(
            self.changelist_url,
            {
                "action": "reactivate_items",
                "confirm_reactivate": "1",
                "reason": "Back in catalogue",
                ACTION_CHECKBOX_NAME: [str(item.pk)],
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        message_text = " ".join(str(message) for message in get_messages(response.wsgi_request))
        self.assertIn("retail price greater than 0", message_text)
        item.refresh_from_db()
        self.assertFalse(item.is_active)


class AddItemCommandTests(TestCase):
    def setUp(self):
        self.family = create_family("CLI family")
        self.supplier = create_supplier(name="CLI Supplier")

    def test_add_item_activate_zero_retail_raises_without_creating_row(self):
        with self.assertRaises(CommandError) as raised:
            call_command(
                "add_item",
                "Orphan test",
                family=self.family.name,
                vat_rate="VAT16",
                internal_code="CLI-ORPHAN",
                retail_price="0",
                supplier=self.supplier.name,
                cost_price="5.00",
                activate=True,
            )

        self.assertIn("retail-price must be greater than 0", str(raised.exception))
        self.assertFalse(Item.objects.filter(internal_code="CLI-ORPHAN").exists())

    def test_add_item_activate_creates_active_item(self):
        call_command(
            "add_item",
            "Activated item",
            family=self.family.name,
            vat_rate="VAT16",
            internal_code="CLI-ACTIVE",
            retail_price="12.50",
            supplier=self.supplier.name,
            cost_price="8.50",
            activate=True,
            verbosity=0,
        )

        item = Item.objects.get(internal_code="CLI-ACTIVE")
        self.assertTrue(item.is_active)
        self.assertEqual(item.retail_price, Decimal("12.50"))
        self.assertTrue(
            SupplierItemPrice.objects.filter(item=item, primary=True).exists()
        )

    def test_add_item_with_sub_family(self):
        sub_family = create_sub_family("Bags", self.family)
        call_command(
            "add_item",
            "Bagged cement",
            family=self.family.name,
            vat_rate="VAT16",
            internal_code="CLI-BAG",
            retail_price="9.50",
            sub_family="Bags",
            verbosity=0,
        )

        item = Item.objects.get(internal_code="CLI-BAG")
        self.assertEqual(item.sub_family_id, sub_family.pk)


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

    def test_admin_can_toggle_family_is_active(self):
        family = create_family("Cement", is_active=True)
        self.client.force_login(self.superuser)
        url = reverse("admin:products_familyproduct_change", args=[family.pk])

        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        data = {"is_active": "", "_save": "Save"}
        for inline in response.context["inline_admin_formsets"]:
            prefix = inline.formset.prefix
            data[f"{prefix}-TOTAL_FORMS"] = inline.formset.total_form_count()
            data[f"{prefix}-INITIAL_FORMS"] = inline.formset.initial_form_count()
            data[f"{prefix}-MIN_NUM_FORMS"] = inline.formset.min_num
            data[f"{prefix}-MAX_NUM_FORMS"] = inline.formset.max_num

        response = self.client.post(url, data)

        self.assertEqual(response.status_code, 302)
        family.refresh_from_db()
        self.assertFalse(family.is_active)
        self.assertEqual(family.name, "Cement")


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
        self.supplier = self.create_test_supplier()

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

    def test_console_header_uses_settings_popover(self):
        self.client.force_login(self.staff_user)

        response = self.client.get(reverse("item_console"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="settings-toggle"')
        self.assertContains(response, 'id="settings-popover"')
        self.assertNotContains(response, 'id="language-select"')
        self.assertNotContains(response, 'id="theme-toggle"')
        self.assertContains(response, self.staff_user.email)
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

    def test_console_js_omits_grid_lifecycle_buttons(self):
        source = (settings.BASE_DIR / "products/static/products/js/console.js").read_text()
        self.assertNotIn("actions.appendChild(lifeButton)", source)
        self.assertIn('getElementById("drawer-lifecycle")', source)

    def test_console_header_groups_master_data_buttons(self):
        self.client.force_login(self.staff_user)

        response = self.client.get(reverse("item_console"))
        html = response.content.decode()

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="master-data-cluster"')
        self.assertContains(response, 'id="master-data-toggle"')
        self.assertContains(response, 'id="manage-families"')
        self.assertContains(response, 'id="manage-sub-families"')
        self.assertContains(response, 'id="manage-suppliers"')
        self.assertRegex(
            html,
            r'id="master-data-cluster"[\s\S]*id="manage-families"[\s\S]*id="settings-toggle"',
        )
        self.assertRegex(
            html,
            r'id="bulk-apply"[\s\S]*id="new-item"',
        )
        self.assertNotRegex(
            html,
            r'id="bulk-apply"[\s\S]*id="manage-families"[\s\S]*id="new-item"',
        )

    def test_staff_can_open_dashboard(self):
        self.client.force_login(self.staff_user)

        response = self.client.get(reverse("staff_dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="pref-language"')
        self.assertContains(response, 'id="pref-theme"')
        self.assertContains(response, 'class="dash-card"')
        self.assertContains(response, 'data-i18n="cardItemConsole"')
        self.assertContains(response, 'data-i18n="sectionWarehouse"')
        self.assertContains(response, 'data-i18n="sectionVisualizations"')
        # Warehouse cards (all groups)
        self.assertContains(response, 'href="/manage/items/"')
        self.assertContains(response, 'href="/manage/catalog/"')
        self.assertContains(response, 'href="/manage/cost-trends/"')
        self.assertContains(response, 'href="/manage/purchase-orders/"')
        self.assertContains(response, 'href="/manage/goods-receipts/"')
        self.assertContains(response, 'href="/manage/internal-requests/"')
        self.assertContains(response, 'href="/manage/threads/"')
        # Admin-only cards visible for warehouse admin
        self.assertContains(response, 'href="/manage/approval-limits/"')
        self.assertContains(response, 'href="/manage/branch-approval-limits/"')
        # Branch cards hidden: staff_user has no branch membership
        self.assertNotContains(response, 'href="/branch/select/"')
        self.assertNotContains(response, 'href="/branch/catalog/"')
        self.assertNotContains(response, 'href="/branch/requests/"')
        self.assertNotContains(response, 'href="/branch/receipts/"')
        # Developer reference still on the page (collapsed)
        self.assertContains(response, "Developer reference")
        self.assertContains(response, "/api/manage/suppliers/")
        self.assertContains(response, "/api/manage/catalog/")
        self.assertContains(response, "/api/manage/approval-limits/")
        self.assertContains(response, "/api/manage/internal-requests/")
        self.assertContains(response, "/api/manage/branch-approval-limits/")
        self.assertContains(response, "/api/branch/catalog/")
        self.assertContains(response, "/api/branch/requests/")
        self.assertContains(response, "/api/branch/receipts/issues/")
        self.assertContains(response, "/api/branch/stock/adjust/")
        self.assertContains(response, "/api/manage/purchase-orders/&lt;id&gt;/reopen/")
        self.assertContains(response, "/api/manage/purchase-orders/&lt;id&gt;/cancel/")
        self.assertContains(response, 'id="settings-toggle"')
        self.assertContains(response, 'id="settings-popover"')
        self.assertNotContains(response, 'id="language-select"')
        self.assertNotContains(response, 'id="theme-toggle"')
        self.assertContains(response, reverse("logout"))
        self.assertContains(response, 'id="settings-help"')
        self.assertNotContains(response, 'href="/admin/"')
        self.assertNotContains(response, "/api/items/")
        self.assertContains(response, self.staff_user.email)
        self.assertContains(response, "warehouse_admins")
        self.assertNotContains(response, "products.view_item")
        self.assertNotContains(response, "products.delete_item")

    def test_operator_and_manager_hide_admin_only_cards(self):
        for group in (GROUP_OPERATORS, GROUP_MANAGERS):
            user = make_warehouse_user(f"{group}@example.com", group_name=group)
            self.client.force_login(user)
            response = self.client.get(reverse("staff_dashboard"))
            self.assertEqual(response.status_code, 200)
            # Regular warehouse cards
            self.assertContains(response, 'href="/manage/items/"')
            self.assertContains(response, 'href="/manage/catalog/"')
            self.assertContains(response, 'href="/manage/cost-trends/"')
            self.assertContains(response, 'href="/manage/purchase-orders/"')
            self.assertContains(response, 'href="/manage/goods-receipts/"')
            self.assertContains(response, 'href="/manage/internal-requests/"')
            self.assertContains(response, 'href="/manage/threads/"')
            # Admin-only cards hidden
            self.assertNotContains(response, 'href="/manage/approval-limits/"')
            self.assertNotContains(response, 'href="/manage/branch-approval-limits/"')
            self.assertNotContains(response, 'href="/admin/"')

    def test_branch_membership_user_sees_branch_cards(self):
        from branches.models import Branch
        from branches.services import assign_membership
        from branches.capabilities import ROLE_OPERATOR

        branch = Branch.objects.create(name="Dashboard Test Branch")
        assign_membership(self.staff_user, branch, ROLE_OPERATOR)
        self.client.force_login(self.staff_user)

        response = self.client.get(reverse("staff_dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'href="/branch/catalog/"')
        self.assertContains(response, 'href="/branch/requests/"')
        self.assertContains(response, 'href="/branch/threads/"')
        self.assertContains(response, 'href="/branch/receipts/"')
        self.assertContains(response, 'href="/company-voice/"')
        self.assertNotContains(response, 'href="/branch/select/"')

    def test_superuser_sees_permission_codenames_on_dashboard(self):
        user_model = get_user_model()
        superuser = user_model.objects.create_superuser(
            email="root@example.com",
            password="test-pass-123",
        )
        self.client.force_login(superuser)

        response = self.client.get(reverse("staff_dashboard"))

        self.assertEqual(response.status_code, 200)
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
        self.assertContains(response, 'data-can-add-sub-family="false"')
        self.assertContains(response, 'data-can-change-sub-family="false"')
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
                "add_sub_family": False,
                "change_sub_family": False,
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
        self.assertContains(response, 'data-can-add-sub-family="true"')
        self.assertContains(response, 'data-can-change-sub-family="true"')
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
                "add_sub_family": True,
                "change_sub_family": True,
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
        self.assertIn("suppliers", payload)

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
            data=json.dumps(self.genesis_create_payload(
                description="Console cement",
                unit_of_measure=Item.UnitOfMeasure.KG,
                internal_code="CON-1",
                reorder_level="4",
                retail_price="10.00",
                reason="Added from console",
            )),
            content_type="application/json",
        )

        self.assertEqual(create_response.status_code, 200)
        created = create_response.json()["item"]
        item = Item.objects.get(pk=created["id"])
        self.assertTrue(item.is_active)
        self.assertEqual(item.description, "Console cement")
        self.assertNotIn("stock", created)
        self.assertNotIn("suppliers", created)
        self.assertTrue(
            SupplierItemPrice.objects.filter(item=item, primary=True).exists()
        )
        self.assertEqual(
            item.change_logs.get(action=ItemChangeLog.Action.CREATED).reason,
            "Added from console",
        )

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

    def test_console_api_rejects_invalid_internal_code_format(self):
        self.client.force_login(self.staff_user)

        response = self.client.post(
            reverse("manage_item_list"),
            data=json.dumps(self.genesis_create_payload(
                description="Bad code item",
                unit_of_measure=Item.UnitOfMeasure.KG,
                internal_code="BAD CODE",
            )),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        payload = response.json()
        self.assertEqual(payload["code"], "invalid_internal_code")
        self.assertFalse(Item.objects.filter(description="Bad code item").exists())

    def test_console_create_stores_internal_code_uppercase(self):
        self.client.force_login(self.staff_user)

        response = self.client.post(
            reverse("manage_item_list"),
            data=json.dumps(self.genesis_create_payload(
                description="Lowercase code item",
                unit_of_measure=Item.UnitOfMeasure.KG,
                internal_code="con-lc",
            )),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        created = response.json()["item"]
        self.assertEqual(created["internal_code"], "CON-LC")
        item = Item.objects.get(pk=created["id"])
        self.assertEqual(item.internal_code, "CON-LC")

    def test_console_create_without_internal_code_is_rejected(self):
        self.client.force_login(self.staff_user)

        response = self.client.post(
            reverse("manage_item_list"),
            data=json.dumps(self.genesis_create_payload(
                description="No code item",
                unit_of_measure=Item.UnitOfMeasure.KG,
                internal_code="",
            )),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        payload = response.json()
        self.assertEqual(payload["code"], "item_genesis_not_ready")
        self.assertFalse(Item.objects.filter(description="No code item").exists())

    def test_console_create_with_zero_retail_price_is_rejected(self):
        self.client.force_login(self.staff_user)

        response = self.client.post(
            reverse("manage_item_list"),
            data=json.dumps(self.genesis_create_payload(
                description="Zero retail item",
                unit_of_measure=Item.UnitOfMeasure.KG,
                internal_code="ZERO-1",
                retail_price="0",
            )),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        payload = response.json()
        self.assertEqual(payload["code"], "item_genesis_not_ready")
        self.assertFalse(Item.objects.filter(internal_code="ZERO-1").exists())

    def test_console_update_rejects_internal_code_change(self):
        item = self.create_test_item(
            self.staff_user,
            description="Immutable code",
            internal_code="IMM-1",
        )
        self.client.force_login(self.staff_user)

        response = self.client.patch(
            reverse("manage_item_detail", args=[item.id]),
            data=json.dumps({
                "internal_code": "IMM-2",
            }),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        payload = response.json()
        self.assertEqual(payload["code"], "internal_code_immutable")
        item.refresh_from_db()
        self.assertEqual(item.internal_code, "IMM-1")

    def test_console_update_allows_set_if_empty_internal_code(self):
        item = create_item(
            self.staff_user,
            family=self.family,
            description="Legacy empty code",
            internal_code="",
            unit_of_measure=Item.UnitOfMeasure.PIECE,
            vat_rate=self.vat_rate,
        )
        self.client.force_login(self.staff_user)

        response = self.client.patch(
            reverse("manage_item_detail", args=[item.id]),
            data=json.dumps({
                "internal_code": "LEGACY-API",
            }),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        item.refresh_from_db()
        self.assertEqual(item.internal_code, "LEGACY-API")

        second = self.client.patch(
            reverse("manage_item_detail", args=[item.id]),
            data=json.dumps({
                "internal_code": "LEGACY-2",
            }),
            content_type="application/json",
        )
        self.assertEqual(second.status_code, 400)
        self.assertEqual(second.json()["code"], "internal_code_immutable")

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

    def test_item_create_rejects_bool_family_id(self):
        self.client.force_login(self.staff_user)

        response = self.client.post(
            reverse("manage_item_list"),
            data=json.dumps(self.genesis_create_payload(
                family_id=True,
                description="Bad family id",
            )),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("integer", response.json()["error"].lower())

    def test_bulk_rejects_bool_ids(self):
        self.client.force_login(self.staff_user)

        response = self.client.post(
            reverse("manage_item_bulk"),
            data=json.dumps({
                "action": "reactivate",
                "ids": [True],
                "reason": "x",
            }),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("integer", response.json()["error"].lower())

    def test_item_list_pagination(self):
        self.client.force_login(self.staff_user)
        for i in range(3):
            self.create_test_item(
                self.staff_user,
                description=f"Item {i}",
                internal_code=f"PG-{i}",
            )

        resp = self.client.get(reverse("manage_item_list") + "?page=1&page_size=2")
        self.assertEqual(resp.status_code, 200)
        payload = resp.json()
        self.assertEqual(len(payload["items"]), 2)
        self.assertEqual(payload["total"], 3)
        self.assertEqual(payload["page"], 1)
        self.assertEqual(payload["page_size"], 2)
        self.assertEqual(payload["num_pages"], 2)

        page2 = self.client.get(reverse("manage_item_list") + "?page=2&page_size=2").json()
        self.assertEqual(len(page2["items"]), 1)

    def test_item_list_filters_and_sort(self):
        self.client.force_login(self.staff_user)
        family_b = self.create_test_family("Other Family")
        self.create_test_item(self.staff_user, description="Alpha cement", internal_code="AA")
        self.create_test_item(self.staff_user, description="Beta sand", internal_code="BB", active=False)
        self.create_test_item(self.staff_user, family=family_b, description="Gamma", internal_code="CC")

        self.assertEqual(
            self.client.get(reverse("manage_item_list") + "?q=cement&page=1&page_size=50").json()["total"], 1
        )
        self.assertEqual(
            self.client.get(reverse("manage_item_list") + "?status=active&page=1&page_size=50").json()["total"], 2
        )
        self.assertEqual(
            self.client.get(reverse("manage_item_list") + f"?family_id={family_b.id}&page=1&page_size=50").json()["total"], 1
        )

        resp = self.client.get(reverse("manage_item_list") + "?sort=description&dir=desc&page=1&page_size=50").json()
        self.assertEqual(
            [item["internal_code"] for item in resp["items"]], ["CC", "BB", "AA"]
        )

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

    def test_staff_cannot_rename_family_through_console_api(self):
        family = self.create_test_family("Original")
        self.client.force_login(self.staff_user)

        rename = self.client.patch(
            reverse("manage_family_detail", args=[family.id]),
            data=json.dumps({"name": "Renamed"}),
            content_type="application/json",
        )
        self.assertEqual(rename.status_code, 200)
        family.refresh_from_db()
        self.assertEqual(family.name, "Original")

    def test_staff_can_deactivate_family_through_console_api(self):
        family = self.create_test_family("Original")
        self.client.force_login(self.staff_user)

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
            data=json.dumps(self.genesis_create_payload(
                family_id=family_id,
                description="Family-first item",
                internal_code="FAM-1",
                retail_price="5.00",
            )),
            content_type="application/json",
        )

        self.assertEqual(item_response.status_code, 200)
        item = Item.objects.get(pk=item_response.json()["item"]["id"])
        self.assertEqual(item.family_id, family_id)
        self.assertTrue(item.is_active)

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

    def test_staff_can_create_sub_family_through_console_api(self):
        self.client.force_login(self.staff_user)

        response = self.client.post(
            reverse("manage_sub_family_list"),
            data=json.dumps({"name": "Bags", "family_id": self.family.id}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()["sub_family"]
        self.assertEqual(payload["name"], "Bags")
        self.assertEqual(payload["family"]["id"], self.family.id)

    def test_console_create_sub_family_rejects_empty_and_duplicate_name(self):
        self.client.force_login(self.staff_user)

        empty = self.client.post(
            reverse("manage_sub_family_list"),
            data=json.dumps({"name": "  ", "family_id": self.family.id}),
            content_type="application/json",
        )
        self.assertEqual(empty.status_code, 400)
        self.assertEqual(empty.json()["code"], "sub_family_name_required")

        self.client.post(
            reverse("manage_sub_family_list"),
            data=json.dumps({"name": "Bags", "family_id": self.family.id}),
            content_type="application/json",
        )
        duplicate = self.client.post(
            reverse("manage_sub_family_list"),
            data=json.dumps({"name": "bags", "family_id": self.family.id}),
            content_type="application/json",
        )
        self.assertEqual(duplicate.status_code, 400)
        self.assertEqual(duplicate.json()["code"], "duplicate_sub_family_name")

    def test_staff_cannot_rename_sub_family_through_console_api(self):
        sub_family = create_sub_family("Bags", self.family)
        self.client.force_login(self.staff_user)

        rename = self.client.patch(
            reverse("manage_sub_family_detail", args=[sub_family.id]),
            data=json.dumps({"name": "Bulk"}),
            content_type="application/json",
        )
        self.assertEqual(rename.status_code, 200)
        sub_family.refresh_from_db()
        self.assertEqual(sub_family.name, "Bags")

    def test_item_create_rejects_sub_family_family_mismatch(self):
        other_family = self.create_test_family("Other")
        sub_family = create_sub_family("Steel", other_family)
        self.client.force_login(self.staff_user)

        response = self.client.post(
            reverse("manage_item_list"),
            data=json.dumps(self.genesis_create_payload(
                sub_family_id=sub_family.id,
                description="Mismatch",
                internal_code="MIS-1",
                retail_price="5.00",
            )),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["code"], "sub_family_family_mismatch")

    def test_item_patch_rejects_family_change_with_mismatched_sub_family(self):
        sub_family = create_sub_family("Bags", self.family)
        other_family = self.create_test_family("Pipes")
        item = self.create_test_item(
            self.staff_user,
            description="Bagged cement",
            internal_code="BAG-PATCH",
            sub_family=sub_family,
        )
        self.client.force_login(self.staff_user)

        response = self.client.patch(
            reverse("manage_item_detail", args=[item.id]),
            data=json.dumps({
                "family_id": other_family.id,
                "sub_family_id": sub_family.id,
            }),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["code"], "sub_family_family_mismatch")
        item.refresh_from_db()
        self.assertEqual(item.family_id, self.family.id)
        self.assertEqual(item.sub_family_id, sub_family.id)

    def test_item_patch_can_clear_sub_family_with_null(self):
        sub_family = create_sub_family("Bags", self.family)
        item = self.create_test_item(
            self.staff_user,
            description="Bagged cement",
            internal_code="CLR-SUB",
            sub_family=sub_family,
        )
        self.client.force_login(self.staff_user)

        response = self.client.patch(
            reverse("manage_item_detail", args=[item.id]),
            data=json.dumps({"sub_family_id": None}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        item.refresh_from_db()
        self.assertIsNone(item.sub_family_id)
        self.assertIsNone(response.json()["item"]["sub_family"])

    def test_manage_item_list_includes_sub_families(self):
        sub_family = create_sub_family("Bags", self.family)
        self.client.force_login(self.staff_user)

        payload = self.client.get(reverse("manage_item_list")).json()

        self.assertIn("sub_families", payload)
        names = [row["name"] for row in payload["sub_families"]]
        self.assertIn(sub_family.name, names)

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
        self.assertNotIn("items", self.client.get(reverse("manage_supplier_list")).json())

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
        create_family("cimento")

        call_command("seed_dev_data", verbosity=0)

        self.assertTrue(
            get_user_model().objects.filter(
                email="armazem.admin@centcompras.dev",
            ).exists()
        )
        item = Item.objects.get(internal_code="CEM-50")
        self.assertEqual(item.family.name, "cimento")
        self.assertEqual(
            FamilyProduct.objects.filter(name__iexact="Cimento").count(),
            1,
        )
        self.assertEqual(item.sub_family.name, "Sacos")

    def test_second_seed_keeps_legacy_family_inactive(self):
        call_command("seed_dev_data", verbosity=0)
        legacy = FamilyProduct.objects.get(name="Stock legado")
        self.assertFalse(legacy.is_active)

        call_command("seed_dev_data", verbosity=0)
        legacy.refresh_from_db()
        self.assertFalse(legacy.is_active)
        self.assertNotIn(
            "LEG-001",
            {item.internal_code for item in get_catalog()},
        )

    def test_seed_gives_every_active_item_one_primary_supplier(self):
        call_command("seed_dev_data", verbosity=0)

        active_items = Item.objects.filter(is_active=True)
        self.assertGreater(active_items.count(), 0)
        for item in active_items:
            primaries = SupplierItemPrice.objects.filter(item=item, primary=True)
            self.assertEqual(
                primaries.count(),
                1,
                msg=f"{item.internal_code} should have exactly one primary supplier",
            )
            self.assertGreater(primaries.get().cost_price, 0)

    def test_seed_cost_trends_demo_on_cem50(self):
        call_command("seed_dev_data", verbosity=0)
        item = Item.objects.get(internal_code="CEM-50")
        timeline = build_item_primary_cost_timeline(item)
        costs = [point["cost"] for point in timeline]
        self.assertIn(Decimal("8.50"), costs)
        self.assertIn(Decimal("9.45"), costs)
        self.assertGreaterEqual(len(timeline), 4)


class CostTrendSeriesTests(ItemTestCaseMixin, TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            email="cost-trends@example.com",
            password="test-pass-123",
        )
        assign_warehouse_group(self.user, GROUP_ADMINS)
        self.client = Client()
        self.family = self.create_test_family()
        self.supplier = self.create_test_supplier()
        self.item = self.create_test_item(
            self.user,
            internal_code="TREND-1",
            description="Trend item",
        )
        self.sip = SupplierItemPrice.objects.get(item=self.item, primary=True)

    def test_build_timeline_records_cost_steps(self):
        update_supplier_item_price(
            self.sip, user=self.user, cost_price=Decimal("11.00")
        )
        update_supplier_item_price(
            self.sip, user=self.user, cost_price=Decimal("12.00")
        )
        timeline = build_item_primary_cost_timeline(self.item)
        costs = [point["cost"] for point in timeline]
        self.assertEqual(costs[0], Decimal("5.00"))
        self.assertEqual(costs[-1], Decimal("12.00"))
        self.assertEqual(len(costs), 3)

    def test_resolve_cost_trend_window_rejects_unknown_period(self):
        with self.assertRaises(ValidationError) as ctx:
            resolve_cost_trend_window("last_year")
        self.assertEqual(ctx.exception.code, "invalid_period")

    def test_get_item_primary_cost_series_summary(self):
        from datetime import timedelta

        from django.utils import timezone

        update_supplier_item_price(
            self.sip, user=self.user, cost_price=Decimal("11.00")
        )
        start = timezone.now() - timedelta(days=1)
        end = timezone.now() + timedelta(hours=1)
        payload = get_item_primary_cost_series(
            self.item,
            start=start,
            end=end,
            period="last_1_day",
        )
        self.assertEqual(payload["summary"]["start_cost"], "5.00")
        self.assertEqual(payload["summary"]["end_cost"], "11.00")
        self.assertEqual(payload["summary"]["change_pct"], "120.00")

    def test_cost_series_api_requires_login(self):
        response = self.client.get(
            reverse("manage_item_cost_series", args=[self.item.id]),
            {"period": "last_30_days"},
        )
        self.assertEqual(response.status_code, 401)

    def test_cost_series_api_returns_points(self):
        self.client.force_login(self.user)
        response = self.client.get(
            reverse("manage_item_cost_series", args=[self.item.id]),
            {"period": "last_30_days"},
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["item"]["internal_code"], "TREND-1")
        self.assertIn("points", data)
        self.assertIn("summary", data)

    def test_cost_trends_page_renders(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("cost_trends_console"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="cost-chart"')
        self.assertContains(response, 'id="cost-period"')
        self.assertContains(response, 'id="cost-item"')


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

    def test_create_item_rejects_empty_description(self):
        with self.assertRaises(DescriptionRequiredError):
            create_item(
                self.user,
                family=self.family,
                description="   ",
                unit_of_measure=Item.UnitOfMeasure.PIECE,
                vat_rate=self.vat_rate,
            )

    def test_update_item_rejects_empty_description(self):
        item = self.create_test_item(self.user, description="OK")

        with self.assertRaises(DescriptionRequiredError):
            update_item(self.user, item, description="   ")

    def test_create_item_rejects_negative_selling_prices(self):
        for field in ("retail_price", "wholesale_price", "special_price"):
            with self.assertRaises(InvalidSellingPriceError):
                create_item(
                    self.user,
                    family=self.family,
                    description="OK",
                    unit_of_measure=Item.UnitOfMeasure.PIECE,
                    vat_rate=self.vat_rate,
                    **{field: "-1"},
                )

    def test_create_item_rejects_nan_and_infinite_prices(self):
        for value in ("NaN", "Infinity", "-Infinity"):
            with self.assertRaises(InvalidSellingPriceError):
                create_item(
                    self.user,
                    family=self.family,
                    description="OK",
                    unit_of_measure=Item.UnitOfMeasure.PIECE,
                    vat_rate=self.vat_rate,
                    retail_price=value,
                )

    def test_create_item_rejects_negative_reorder_level(self):
        with self.assertRaises(InvalidReorderLevelError):
            create_item(
                self.user,
                family=self.family,
                description="OK",
                unit_of_measure=Item.UnitOfMeasure.PIECE,
                vat_rate=self.vat_rate,
                reorder_level="-1",
            )

    def test_update_item_rejects_negative_selling_price(self):
        item = self.create_test_item(self.user, description="OK")

        with self.assertRaises(InvalidSellingPriceError):
            update_item(self.user, item, retail_price="-5")

    def test_update_item_rejects_negative_reorder_level(self):
        item = self.create_test_item(self.user, description="OK")

        with self.assertRaises(InvalidReorderLevelError):
            update_item(self.user, item, reorder_level="-1")

    def test_create_item_allows_zero_prices_and_reorder(self):
        item = create_item(
            self.user,
            family=self.family,
            description="Free item",
            unit_of_measure=Item.UnitOfMeasure.PIECE,
            vat_rate=self.vat_rate,
            retail_price="0",
            wholesale_price="0",
            special_price="0",
            reorder_level="0",
        )
        self.assertEqual(item.retail_price, Decimal("0"))
        self.assertEqual(item.reorder_level, Decimal("0"))

    def test_vat_rate_rejects_out_of_range(self):
        from django.db import IntegrityError, transaction

        for rate in ("-0.1", "1.5"):
            with self.assertRaises(IntegrityError), transaction.atomic():
                VatRate.objects.create(
                    code=f"VAT-BAD-{rate}",
                    label="Bad",
                    rate=rate,
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
            with_primary_supplier=False,
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

    def test_primary_unique_violation_reports_primary_error(self):
        from products.services import (
            DuplicatePrimarySupplierItemPriceError,
            _save_supplier_item_price,
        )

        other_supplier = create_supplier(name="Porto Materials Co")
        create_supplier_item_price(
            self.supplier, self.item, "12.50", primary=True, user=self.user
        )

        duplicate_primary = SupplierItemPrice(
            supplier=other_supplier,
            item=self.item,
            cost_price=Decimal("11.00"),
            primary=True,
        )
        with self.assertRaises(DuplicatePrimarySupplierItemPriceError):
            _save_supplier_item_price(duplicate_primary)

    def test_negative_cost_price_is_rejected(self):
        with self.assertRaises(InvalidCostPriceError):
            create_supplier_item_price(self.supplier, self.item, "-1")

    def test_create_supplier_item_price_rejects_inactive_supplier(self):
        update_supplier(self.supplier, user=self.user, is_active=False)

        with self.assertRaises(InactiveSupplierError):
            create_supplier_item_price(self.supplier, self.item, "12.50")

    def test_create_supplier_item_price_rejects_inactive_item(self):
        deactivate_item(self.user, self.item, reason="discontinued")

        with self.assertRaises(InactiveItemError):
            create_supplier_item_price(self.supplier, self.item, "12.50")

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
        from accounts.capabilities import can_mutate_catalog

        operator = make_warehouse_user("op-sip@example.com", group_name=GROUP_OPERATORS)
        self.assertTrue(operator.has_perm("products.view_supplieritemprice"))
        self.assertTrue(operator.has_perm("products.add_supplieritemprice"))
        self.assertTrue(operator.has_perm("products.change_supplieritemprice"))
        self.assertFalse(can_mutate_catalog(operator))

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
            with_primary_supplier=False,
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
            data=json.dumps(self.genesis_create_payload(
                description="Priced item",
                internal_code="PRICE-1",
                retail_price="99.99",
                wholesale_price="75.00",
                special_price="60.00",
            )),
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
            with_primary_supplier=False,
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

    def test_catalog_below_reorder_uses_available_not_on_hand(self):
        item = get_catalog().get(pk=self.item.pk)
        item.quantity = Decimal("20")
        item.reorder_level = Decimal("10")
        item.reserved = Decimal("15")
        self.assertTrue(catalog_below_reorder(item))
        item.reserved = Decimal("5")
        self.assertFalse(catalog_below_reorder(item))

    def test_catalog_buying_price_ignores_deactivated_supplier(self):
        other = create_supplier(name="Porto Materials Co")
        create_supplier_item_price(self.supplier, self.item, "12.50", primary=True)
        create_supplier_item_price(other, self.item, "9.99", primary=False)

        self.supplier.is_active = False
        self.supplier.save()

        item = get_catalog().get(pk=self.item.pk)
        self.assertEqual(catalog_buying_price(item), Decimal("9.99"))

    def test_get_catalog_excludes_items_under_inactive_family(self):
        update_family(self.family, is_active=False)
        self.assertEqual(list(get_catalog()), [])

    def test_get_catalog_active_only_false_includes_deactivated_item(self):
        create_supplier_item_price(
            self.supplier, self.item, "8.50", primary=True, user=self.user
        )
        deactivate_item(self.user, self.item, reason="Removed from catalogue")
        self.assertEqual(list(get_catalog()), [])
        items = list(get_catalog(active_only=False))
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].pk, self.item.pk)
        self.assertFalse(items[0].is_active)

    def test_get_catalog_active_only_false_includes_inactive_family_items(self):
        create_supplier_item_price(
            self.supplier, self.item, "8.50", primary=True, user=self.user
        )
        update_family(self.family, is_active=False)
        items = list(get_catalog(active_only=False))
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].pk, self.item.pk)

    def test_create_item_rejects_inactive_family(self):
        inactive = create_family("Legacy", is_active=False)
        with self.assertRaises(InactiveFamilyError):
            create_item(
                self.user,
                family=inactive,
                description="Should fail",
                unit_of_measure=Item.UnitOfMeasure.PIECE,
                vat_rate=self.vat_rate,
            )

    def test_update_item_rejects_inactive_family(self):
        inactive = create_family("Legacy", is_active=False)
        with self.assertRaises(InactiveFamilyError):
            update_item(self.user, self.item, family=inactive)


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
            with_primary_supplier=False,
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

    def test_catalog_header_uses_settings_popover(self):
        self.client.force_login(self.staff_user)
        response = self.client.get(reverse("catalog_console"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="settings-toggle"')
        self.assertContains(response, 'id="settings-popover"')
        self.assertNotContains(response, 'id="language-select"')
        self.assertNotContains(response, 'id="theme-toggle"')
        self.assertContains(response, self.staff_user.email)
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
        self.assertEqual(Decimal(row["reserved"]), Decimal("0"))
        self.assertEqual(Decimal(row["available"]), Decimal("0"))
        self.assertEqual(Decimal(row["reorder_level"]), Decimal("10"))
        self.assertEqual(Decimal(row["buying_price"]), Decimal("8.50"))
        self.assertTrue(row["below_reorder"])
        self.assertEqual(row["suppliers"][0]["name"], self.supplier.name)
        self.assertTrue(row["suppliers"][0]["primary"])
        self.assertIsNone(row["sub_family"])

    def test_catalog_api_includes_sub_family_when_set(self):
        sub_family = create_sub_family("Bags", self.family)
        self.item.sub_family = sub_family
        self.item.save(update_fields=["sub_family"])
        self.client.force_login(self.staff_user)

        row = self.client.get(reverse("manage_catalog_list")).json()["catalog"][0]

        self.assertEqual(row["sub_family"]["name"], "Bags")

    def test_catalog_api_filters_by_sub_family_id(self):
        sub_family = create_sub_family("Bags", self.family)
        self.item.sub_family = sub_family
        self.item.save(update_fields=["sub_family"])
        other = self.create_test_item(
            self.staff_user,
            description="Other item",
            internal_code="OTHER-1",
        )
        self.client.force_login(self.staff_user)

        response = self.client.get(
            reverse("manage_catalog_list") + f"?sub_family_id={sub_family.id}"
        )

        self.assertEqual(response.status_code, 200)
        codes = [row["internal_code"] for row in response.json()["catalog"]]
        self.assertEqual(codes, ["CEM-50"])
        self.assertNotIn(other.internal_code, codes)

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

    def test_catalog_api_excludes_inactive_items_by_default(self):
        deactivate_item(self.staff_user, self.item, reason="Removed from catalogue")
        self.client.force_login(self.staff_user)
        response = self.client.get(reverse("manage_catalog_list"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["catalog"], [])

    def test_catalog_api_include_inactive_returns_deactivated_items(self):
        deactivate_item(self.staff_user, self.item, reason="Removed from catalogue")
        self.client.force_login(self.staff_user)
        response = self.client.get(reverse("manage_catalog_list") + "?include_inactive=1")
        self.assertEqual(response.status_code, 200)
        catalog = response.json()["catalog"]
        self.assertEqual(len(catalog), 1)
        self.assertEqual(catalog[0]["internal_code"], "CEM-50")
        self.assertFalse(catalog[0]["is_active"])

    def test_catalog_api_suppliers_primary_first(self):
        other = create_supplier(name="AAA Supplies")
        create_supplier_item_price(
            other, self.item, "9.00", primary=False, user=self.staff_user
        )
        self.client.force_login(self.staff_user)
        row = self.client.get(reverse("manage_catalog_list")).json()["catalog"][0]
        self.assertEqual(len(row["suppliers"]), 2)
        self.assertTrue(row["suppliers"][0]["primary"])
        self.assertEqual(row["suppliers"][0]["name"], self.supplier.name)

    def test_catalog_console_has_include_inactive_and_sortable_headers(self):
        self.client.force_login(self.staff_user)
        response = self.client.get(reverse("catalog_console"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="catalog-include-inactive"')
        self.assertContains(response, "th-sortable")
        self.assertContains(response, 'data-sort="internal_code"')
        self.assertContains(response, "catalog.js?v=7")
        self.assertContains(response, "catalog_i18n.js?v=8")


class LanguageCodeContractTests(SimpleTestCase):
    """The dashboard language <select> must resolve in every i18n dictionary.

    Django tests never execute console JS, so the 24 Aug 2026 move of the
    selector from Settings (`value="pt-PT"`) to the dashboard (`value="pt"`)
    shipped green: pages still contained `#pref-language`, and consoles no
    longer contained `#language-select`. `t()` then did
    `CONSOLE_I18N["pt"] || CONSOLE_I18N.en` and stayed in English.

    These tests evaluate the real dictionaries in Node so a code/key mismatch
    fails the suite.
    """

    _LOAD_JS = r"""
const fs = require("fs");
const vm = require("vm");
const src = fs.readFileSync(process.argv[1], "utf8") + "\nthis.__export = " + process.argv[2] + ";";
const ctx = {
    window: {},
    document: {
        readyState: "complete",
        querySelectorAll: () => [],
        getElementById: () => null,
        documentElement: { lang: "en", setAttribute() {} },
        addEventListener() {},
    },
    localStorage: { getItem: () => null, setItem() {} },
};
ctx.window = ctx;
vm.createContext(ctx);
vm.runInContext(src, ctx);
if (ctx.__export === undefined) {
    process.stderr.write("missing binding " + process.argv[2] + "\n");
    process.exit(2);
}
process.stdout.write(JSON.stringify(ctx.__export));
"""

    def _load_js_binding(self, path, binding):
        result = subprocess.run(
            ["node", "-e", self._LOAD_JS, str(path), binding],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(
            result.returncode,
            0,
            f"failed to evaluate {path.name} ({binding}): {result.stderr}",
        )
        return json.loads(result.stdout)

    def _dashboard_lang_codes(self):
        html = (
            settings.BASE_DIR / "products/templates/products/includes/preferences_bar.html"
        ).read_text()
        values = re.findall(r'<option value="([^"]+)">', html)
        self.assertEqual(set(values), {"en", "pt"}, html)
        return values

    def test_dashboard_select_values_resolve_in_warehouse_i18n(self):
        codes = self._dashboard_lang_codes()
        files = [
            (
                settings.BASE_DIR / "products/static/products/js/console_i18n.js",
                "CONSOLE_I18N",
            ),
            (
                settings.BASE_DIR / "products/static/products/js/catalog_i18n.js",
                "CATALOG_I18N",
            ),
            (
                settings.BASE_DIR / "inventory/static/inventory/js/goods_receipts_i18n.js",
                "GR_I18N",
            ),
            (
                settings.BASE_DIR
                / "procurement/static/procurement/js/purchase_orders_i18n.js",
                "PO_I18N",
            ),
            (
                settings.BASE_DIR / "company_voice/static/company_voice/js/feed_i18n.js",
                "window.COMPANY_VOICE_I18N",
            ),
        ]
        for path, binding in files:
            with self.subTest(file=path.name):
                dictionary = self._load_js_binding(path, binding)
                self.assertIn("en", dictionary)
                for code in codes:
                    self.assertIn(
                        code,
                        dictionary,
                        f"{path.name} has no key {code!r}; "
                        f"dashboard <select> stores cc-lang={code!r}. "
                        f"Keys: {sorted(dictionary)}",
                    )
                    self.assertTrue(
                        dictionary[code].get("title"),
                        f"{path.name}[{code!r}] is missing title",
                    )
                self.assertNotEqual(
                    dictionary["pt"]["title"],
                    dictionary["en"]["title"],
                    f"{path.name} Portuguese title is identical to English "
                    "(lookup probably fell through)",
                )
                # Legacy Settings popover value must still resolve.
                self.assertEqual(
                    dictionary["pt"]["title"],
                    dictionary["pt-PT"]["title"],
                )

    def test_preferences_bar_normalizes_legacy_pt_PT(self):
        source = (
            settings.BASE_DIR / "products/static/products/js/preferences_bar.js"
        ).read_text()
        self.assertIn("function normalizeLang", source)
        self.assertIn('startsWith("pt")', source)

    def test_preferences_bar_includes_dashboard_card_keys(self):
        source = (
            settings.BASE_DIR / "products/static/products/js/preferences_bar.js"
        ).read_text()
        self.assertIn("cardItemConsole:", source)
        self.assertIn("cardCostTrends:", source)
        self.assertIn("sectionVisualizations:", source)
        self.assertIn("Gestão de artigos", source)
        self.assertIn("sectionWarehouse:", source)
