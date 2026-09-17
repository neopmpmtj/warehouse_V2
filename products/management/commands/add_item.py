from decimal import Decimal, InvalidOperation

from django.core.management.base import BaseCommand, CommandError

from products.models import FamilyProduct, Item, SubFamily, Supplier, VatRate
from products.services import (
    GenesisSupplierCostPairError,
    ItemGenesisNotReadyError,
    create_and_activate_item,
    create_item,
    get_families,
)


class Command(BaseCommand):
    help = "Add a new item (dev/bootstrap; audit user is null)"

    def add_arguments(self, parser):
        parser.add_argument("description", type=str)
        parser.add_argument(
            "--family",
            required=True,
            help="Family name (must exist)",
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
            required=True,
            help="Warehouse internal code (required; stored as uppercase)",
        )
        parser.add_argument(
            "--sub-family",
            dest="sub_family",
            default="",
            help="Optional sub-family name (resolved within --family)",
        )
        parser.add_argument(
            "--retail-price",
            dest="retail_price",
            default="0",
            help="Retail selling price (default: 0)",
        )
        parser.add_argument(
            "--reorder-level",
            dest="reorder_level",
            default="0",
            help="Reorder level as a whole number (default: 0)",
        )
        parser.add_argument(
            "--supplier",
            default="",
            help="Optional supplier name for Genesis primary buying-price row",
        )
        parser.add_argument(
            "--cost-price",
            dest="cost_price",
            default="",
            help="Optional buying cost for Genesis primary (requires --supplier)",
        )
        parser.add_argument(
            "--activate",
            action="store_true",
            help="Activate in the catalogue after create (reason: Genesis)",
        )

    def handle(self, *args, **options):
        family_name = options["family"].strip()
        family = FamilyProduct.objects.filter(name__iexact=family_name).first()
        if family is None:
            available = ", ".join(
                get_families(active_only=False).values_list("name", flat=True)
            )
            raise CommandError(
                f"Family '{family_name}' not found. Available: {available}"
            )

        sub_family = None
        sub_family_name = (options.get("sub_family") or "").strip()
        if sub_family_name:
            sub_family = SubFamily.objects.filter(
                family=family,
                name__iexact=sub_family_name,
            ).first()
            if sub_family is None:
                available = ", ".join(
                    SubFamily.objects.filter(family=family)
                    .order_by("name")
                    .values_list("name", flat=True)
                )
                raise CommandError(
                    f"Sub-family '{sub_family_name}' not found in family "
                    f"'{family.name}'. Available: {available or '(none)'}"
                )

        vat_rate_code = options["vat_rate"].strip()
        vat_rate = VatRate.objects.filter(code=vat_rate_code).first()
        if vat_rate is None:
            available = ", ".join(VatRate.objects.values_list("code", flat=True))
            raise CommandError(
                f"VAT rate '{vat_rate_code}' not found. Available: {available}"
            )

        item_kwargs = {
            "user": None,
            "family": family,
            "description": options["description"],
            "unit_of_measure": options["unit"],
            "vat_rate": vat_rate,
            "internal_code": options["internal_code"],
            "reorder_level": options["reorder_level"],
            "retail_price": options["retail_price"],
            "sub_family": sub_family,
        }

        if options["activate"]:
            supplier_name = (options.get("supplier") or "").strip()
            cost_price_raw = (options.get("cost_price") or "").strip()
            has_supplier = bool(supplier_name)
            has_cost = bool(cost_price_raw)
            if has_supplier != has_cost:
                raise CommandError(
                    "Pass both --supplier and --cost-price together, or omit both."
                )
            if has_supplier:
                supplier = Supplier.objects.filter(name__iexact=supplier_name).first()
                if supplier is None:
                    available = ", ".join(
                        Supplier.objects.filter(is_active=True)
                        .order_by("name")
                        .values_list("name", flat=True)
                    )
                    raise CommandError(
                        f"Supplier '{supplier_name}' not found. Active: {available}"
                    )
                item_kwargs["supplier"] = supplier
                item_kwargs["cost_price"] = cost_price_raw
            try:
                item = create_and_activate_item(**item_kwargs)
            except (ItemGenesisNotReadyError, GenesisSupplierCostPairError) as exc:
                raise CommandError(exc.messages[0]) from exc
        else:
            item = create_item(**item_kwargs)

        status = "active" if item.is_active else "inactive"
        self.stdout.write(
            self.style.SUCCESS(
                f"Item created ({status}): ID={item.id}, "
                f"{item.internal_code} — {item.description}"
            )
        )
