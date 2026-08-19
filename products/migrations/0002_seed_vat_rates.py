from decimal import Decimal

from django.db import migrations


VAT_RATES = [
    ("VAT01", "1%", Decimal("0.01")),
    ("VAT03", "3%", Decimal("0.03")),
    ("VAT07", "7%", Decimal("0.07")),
    ("VAT16", "16%", Decimal("0.16")),
    ("VAT_EXEMPT", "Exempt", Decimal("0.00")),
]


def seed_vat_rates(apps, schema_editor):
    VatRate = apps.get_model("products", "VatRate")
    for code, label, rate in VAT_RATES:
        VatRate.objects.create(code=code, label=label, rate=rate)


def unseed_vat_rates(apps, schema_editor):
    VatRate = apps.get_model("products", "VatRate")
    codes = [row[0] for row in VAT_RATES]
    VatRate.objects.filter(code__in=codes).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("products", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed_vat_rates, unseed_vat_rates),
    ]
