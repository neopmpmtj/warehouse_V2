from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from decimal import Decimal

from accounts.groups import (
    GROUP_ADMINS,
    WAREHOUSE_USERS,
    assign_warehouse_group,
)
from accounts.models import DEFAULT_USER_TIMEZONE
from products.models import (
    FamilyProduct,
    Item,
    Supplier,
    SupplierItemPrice,
    VatRate,
)
from products.seed_catalog_data import (
    FAMILIES,
    ITEMS,
    SUPPLIERS,
    SUPPLIER_ITEM_PRICES,
)
from products.services import (
    create_family,
    create_item,
    create_supplier,
    create_supplier_item_price,
    reactivate_item,
    update_family,
    update_item,
    update_supplier,
    update_supplier_item_price,
)


DEFAULT_PASSWORD = "devpass123"


def _demo_selling_prices(internal_code):
    total = sum(ord(ch) for ch in internal_code)
    retail = Decimal(10) + (total % 91)
    wholesale = (retail * Decimal("0.80")).quantize(Decimal("0.01"))
    special = (retail * Decimal("0.65")).quantize(Decimal("0.01"))
    return retail, wholesale, special


class Command(BaseCommand):
    help = (
        "Seed local dev data: warehouse users (3 groups), families, "
        "suppliers, and ~50 items (idempotent)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--password",
            default=DEFAULT_PASSWORD,
            help=f"Password for seeded warehouse users (default: {DEFAULT_PASSWORD})",
        )
        parser.add_argument(
            "--skip-items",
            action="store_true",
            help="Only seed the warehouse users.",
        )
        parser.add_argument(
            "--skip-products",
            action="store_true",
            dest="skip_items",
            help="Deprecated alias for --skip-items.",
        )
        parser.add_argument(
            "--skip-warehouse",
            action="store_true",
            help="Do not create warehouse users.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        password = options["password"]
        user_model = get_user_model()

        warehouse_user = None
        if not options["skip_warehouse"]:
            for email, group_name in WAREHOUSE_USERS:
                user, created = user_model.objects.get_or_create(
                    email=email,
                    defaults={
                        "is_staff": False,
                        "is_superuser": False,
                        "timezone": DEFAULT_USER_TIMEZONE,
                    },
                )
                changed_fields = []
                if user.is_staff or user.is_superuser:
                    user.is_staff = False
                    user.is_superuser = False
                    changed_fields.extend(["is_staff", "is_superuser"])
                if not user.timezone:
                    user.timezone = DEFAULT_USER_TIMEZONE
                    changed_fields.append("timezone")
                if created or not user.check_password(password):
                    user.set_password(password)
                    changed_fields.append("password")
                if changed_fields:
                    user.save(update_fields=changed_fields)
                assign_warehouse_group(user, group_name)
                if group_name == GROUP_ADMINS:
                    warehouse_user = user
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Warehouse user: {user.email} (group {group_name})"
                    )
                )

        if not options["skip_items"]:
            families_by_name = {}
            for family_data in FAMILIES:
                existing = FamilyProduct.objects.filter(
                    name__iexact=family_data["name"]
                ).first()
                if existing:
                    family = existing
                    # Keep active while seeding items under this family.
                    if not family.is_active:
                        family = update_family(family, is_active=True)
                    families_by_name[family_data["name"].casefold()] = family
                    self.stdout.write(f"Exists family: {family.name}")
                    continue

                # Create active first so items can be assigned; apply target
                # is_active after the item loop.
                family = create_family(family_data["name"], is_active=True)
                families_by_name[family_data["name"].casefold()] = family
                self.stdout.write(f"Created family: {family.name}")

            for supplier_data in SUPPLIERS:
                existing = Supplier.objects.filter(
                    name__iexact=supplier_data["name"]
                ).first()
                if existing:
                    supplier = existing
                    if supplier.is_active != supplier_data["is_active"]:
                        update_supplier(
                            supplier,
                            is_active=supplier_data["is_active"],
                        )
                    self.stdout.write(f"Exists supplier: {supplier.name}")
                    continue

                supplier = create_supplier(
                    name=supplier_data["name"],
                    contact_name=supplier_data.get("contact_name", ""),
                    email=supplier_data.get("email", ""),
                    phone=supplier_data.get("phone", ""),
                    notes=supplier_data.get("notes", ""),
                    is_active=supplier_data["is_active"],
                )
                self.stdout.write(
                    self.style.SUCCESS(f"Created supplier: {supplier.name}")
                )

            for row in ITEMS:
                (
                    internal_code,
                    description,
                    family_name,
                    unit,
                    reorder_level,
                    is_active,
                    vat_rate_code,
                ) = row
                family = families_by_name[family_name.casefold()]
                vat_rate = VatRate.objects.filter(code=vat_rate_code).first()
                if vat_rate is None:
                    self.stdout.write(
                        self.style.WARNING(
                            f"Skipping {internal_code}: VAT rate {vat_rate_code} not found"
                        )
                    )
                    continue

                retail, wholesale, special = _demo_selling_prices(internal_code)
                existing = Item.objects.filter(internal_code__iexact=internal_code).first()
                if existing:
                    update_item(
                        warehouse_user,
                        existing,
                        retail_price=retail,
                        wholesale_price=wholesale,
                        special_price=special,
                        reason="seed_dev_data",
                    )
                    self.stdout.write(
                        f"Exists item: {existing.internal_code} — {existing.description}"
                    )
                    continue

                item = create_item(
                    user=warehouse_user,
                    family=family,
                    description=description,
                    unit_of_measure=unit,
                    vat_rate=vat_rate,
                    internal_code=internal_code,
                    reorder_level=reorder_level,
                    retail_price=retail,
                    wholesale_price=wholesale,
                    special_price=special,
                    reason="seed_dev_data",
                )
                if is_active:
                    reactivate_item(warehouse_user, item, reason="Genesis")
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Created item: {item.internal_code} — {item.description}"
                    )
                )

            for family_data in FAMILIES:
                family = families_by_name[family_data["name"].casefold()]
                family.refresh_from_db()
                if family.is_active != family_data["is_active"]:
                    update_family(family, is_active=family_data["is_active"])
                    self.stdout.write(
                        f"Family activity: {family.name} -> {family_data['is_active']}"
                    )

            suppliers_by_name = {
                supplier.name.casefold(): supplier
                for supplier in Supplier.objects.all()
            }
            items_by_code = {
                item.internal_code.casefold(): item
                for item in Item.objects.all()
            }

            for supplier_name, internal_code, cost_price, primary in SUPPLIER_ITEM_PRICES:
                supplier = suppliers_by_name.get(supplier_name.casefold())
                item = items_by_code.get(internal_code.casefold())
                if supplier is None or item is None:
                    self.stdout.write(
                        self.style.WARNING(
                            f"Skipping supplier price {supplier_name}/{internal_code}: not found"
                        )
                    )
                    continue

                existing_sip = SupplierItemPrice.objects.filter(
                    supplier=supplier, item=item
                ).first()
                if existing_sip:
                    update_supplier_item_price(
                        existing_sip,
                        user=warehouse_user,
                        cost_price=cost_price,
                        primary=primary,
                    )
                else:
                    create_supplier_item_price(
                        supplier=supplier,
                        item=item,
                        cost_price=cost_price,
                        primary=primary,
                        user=warehouse_user,
                    )
                self.stdout.write(
                    f"Supplier price: {supplier.name} -> {item.internal_code} @ {cost_price}"
                )

        self.stdout.write("")
        self.stdout.write(self.style.WARNING("Dev login credentials:"))
        self.stdout.write(f"  Password: {password}")
        self.stdout.write("")
        self.stdout.write("Warehouse website (/ and /manage/items/) — not /admin/:")
        for email, group_name in WAREHOUSE_USERS:
            self.stdout.write(f"  {email}  ({group_name})")
        self.stdout.write("")
        self.stdout.write(
            "Django permissions: admins view/add/change/delete; "
            "managers view/add/change; operators view only."
        )
