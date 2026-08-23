from decimal import Decimal

from django.db import migrations, models


def forwards_backfill(apps, schema_editor):
    from inventory.services import backfill_reservations

    backfill_reservations()


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("orders", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="internalrequestline",
            name="quantity_reserved",
            field=models.DecimalField(decimal_places=3, default=Decimal("0"), max_digits=12),
        ),
        migrations.AddConstraint(
            model_name="internalrequestline",
            constraint=models.CheckConstraint(
                condition=models.Q(quantity_reserved__gte=0),
                name="request_line_quantity_reserved_gte_zero",
            ),
        ),
        migrations.AddConstraint(
            model_name="internalrequestline",
            constraint=models.CheckConstraint(
                condition=models.Q(quantity_reserved__lte=models.F("quantity")),
                name="request_line_quantity_reserved_lte_quantity",
            ),
        ),
        migrations.RunPython(forwards_backfill, noop),
    ]
