from django.core.management.base import BaseCommand, CommandError

from products.models import FamilyProduct, Item, VatRate
from products.services import create_item, get_product_families, reactivate_item


class Command(BaseCommand):
    help = "Add a new item (dev/bootstrap; audit user is null)"

    def add_arguments(self, parser):
        parser.add_argument("description", type=str)
        parser.add_argument(
            "--family",
            required=True,
            help="Product family name (must exist)",
        )
        parser.add_argument(
            "--vat-rate",
            dest="vat_rate",
            required=True,
            help="VAT rate code (e.g. VAT16)",
        )
        parser.add_argument(
            "--unit",
            default=Item.UnitOfMeasure.PIECE,
            choices=[choice[0] for choice in Item.UnitOfMeasure.choices],
            help="Unit of measure (default: piece)",
        )
        parser.add_argument(
            "--internal-code",
            dest="internal_code",
            default="",
            help="Optional warehouse internal code",
        )
        parser.add_argument(
            "--reorder-level",
            dest="reorder_level",
            default="0",
            help="Reorder level (default: 0)",
        )
        parser.add_argument(
            "--activate",
            action="store_true",
            help="Activate in the catalogue after create (reason: Genesis)",
        )

    def handle(self, *args, **options):
        family_name = options["family"].strip()
        family = FamilyProduct.objects.filter(name=family_name).first()
        if family is None:
            available = ", ".join(
                get_product_families(active_only=False).values_list("name", flat=True)
            )
            raise CommandError(
                f"Product family '{family_name}' not found. Available: {available}"
            )

        vat_rate_code = options["vat_rate"].strip()
        vat_rate = VatRate.objects.filter(code=vat_rate_code).first()
        if vat_rate is None:
            available = ", ".join(VatRate.objects.values_list("code", flat=True))
            raise CommandError(
                f"VAT rate '{vat_rate_code}' not found. Available: {available}"
            )

        item = create_item(
            user=None,
            family=family,
            description=options["description"],
            unit_of_measure=options["unit"],
            vat_rate=vat_rate,
            internal_code=options["internal_code"],
            reorder_level=options["reorder_level"],
        )

        if options["activate"]:
            reactivate_item(user=None, item=item, reason="Genesis")
            item.refresh_from_db()

        status = "active" if item.is_active else "inactive"
        self.stdout.write(
            self.style.SUCCESS(
                f"Item created ({status}): ID={item.id}, "
                f"{item.internal_code} — {item.description}"
            )
        )
