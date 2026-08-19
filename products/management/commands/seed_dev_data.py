from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

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

WAREHOUSE_USER = ("warehouse@centcompras.dev",)


class Command(BaseCommand):
    help = (
        "Seed local dev data: warehouse staff, product families, "
        "suppliers, and ~50 items (idempotent)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--password",
            default=DEFAULT_PASSWORD,
            help=f"Password for the seeded warehouse user (default: {DEFAULT_PASSWORD})",
        )
        parser.add_argument(
            "--skip-products",
            action="store_true",
            help="Only seed the warehouse user.",
        )
        parser.add_argument(
            "--skip-warehouse",
            action="store_true",
            help="Do not create the warehouse staff user (catalog admin).",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        password = options["password"]
        user_model = get_user_model()

        warehouse_user = None
        if not options["skip_warehouse"]:
            warehouse_user, created = user_model.objects.get_or_create(
                email=WAREHOUSE_USER[0],
                defaults={
                    "is_staff": True,
                    "is_superuser": False,
                },
            )
            if created or not warehouse_user.check_password(password):
                warehouse_user.set_password(password)
                warehouse_user.is_staff = True
                warehouse_user.save(update_fields=["password", "is_staff"])
            self.stdout.write(
                self.style.SUCCESS(
                    f"Warehouse staff: {warehouse_user.email} (catalog admin at /manage/items/)"
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
        if warehouse_user:
            self.stdout.write("")
            self.stdout.write("Warehouse item management (/):")
            self.stdout.write(f"  {warehouse_user.email}")
        self.stdout.write("")
        self.stdout.write(
            "Item add/edit is warehouse staff only (is_staff)."
        )
