from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

from accounts.groups import (
    GROUP_ADMINS,
    WAREHOUSE_USERS,
    assign_warehouse_group,
)
from products.models import FamilyProduct, Item, Supplier, VatRate
from products.seed_catalog_data import (
    FAMILIES,
    ITEMS,
    SUPPLIERS,
)
from products.services import (
    create_item,
    create_product_family,
    create_supplier,
    reactivate_item,
    update_product_family,
    update_supplier,
)


DEFAULT_PASSWORD = "devpass123"


class Command(BaseCommand):
    help = (
        "Seed local dev data: warehouse users (3 groups), product families, "
        "suppliers, and ~50 items (idempotent)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--password",
            default=DEFAULT_PASSWORD,
            help=f"Password for seeded warehouse users (default: {DEFAULT_PASSWORD})",
        )
        parser.add_argument(
            "--skip-products",
            action="store_true",
            help="Only seed the warehouse users.",
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
                    },
                )
                changed_fields = []
                if user.is_staff or user.is_superuser:
                    user.is_staff = False
                    user.is_superuser = False
                    changed_fields.extend(["is_staff", "is_superuser"])
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

        if not options["skip_products"]:
            families_by_name = {}
            for family_data in FAMILIES:
                existing = FamilyProduct.objects.filter(name=family_data["name"]).first()
                if existing:
                    family = existing
                    if family.is_active != family_data["is_active"]:
                        update_product_family(
                            family,
                            is_active=family_data["is_active"],
                        )
                    families_by_name[family.name] = family
                    self.stdout.write(f"Exists family: {family.name}")
                    continue

                family = create_product_family(
                    family_data["name"],
                    is_active=family_data["is_active"],
                )
                families_by_name[family.name] = family
                self.stdout.write(f"Created family: {family.name}")

            for supplier_data in SUPPLIERS:
                existing = Supplier.objects.filter(name=supplier_data["name"]).first()
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
                family = families_by_name[family_name]
                vat_rate = VatRate.objects.filter(code=vat_rate_code).first()
                if vat_rate is None:
                    self.stdout.write(
                        self.style.WARNING(
                            f"Skipping {internal_code}: VAT rate {vat_rate_code} not found"
                        )
                    )
                    continue

                existing = Item.objects.filter(internal_code=internal_code).first()
                if existing:
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
                    reason="seed_dev_data",
                )
                if is_active:
                    reactivate_item(warehouse_user, item, reason="Genesis")
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Created item: {item.internal_code} — {item.description}"
                    )
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
