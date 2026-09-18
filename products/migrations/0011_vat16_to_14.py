from decimal import Decimal

from django.db import migrations


def forwards(apps, schema_editor):
    VatRate = apps.get_model("products", "VatRate")
    VatRate.objects.filter(code="VAT16").update(label="14%", rate=Decimal("0.14"))


def backwards(apps, schema_editor):
    VatRate = apps.get_model("products", "VatRate")
    VatRate.objects.filter(code="VAT16").update(label="16%", rate=Decimal("0.16"))


class Migration(migrations.Migration):

    dependencies = [
        ("products", "0010_integer_quantities"),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
