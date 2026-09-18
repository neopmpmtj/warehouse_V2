from django.db import migrations


def forwards(apps, schema_editor):
    VatRate = apps.get_model("products", "VatRate")
    VatRate.objects.filter(code="VAT16").update(code="VAT14")


def backwards(apps, schema_editor):
    VatRate = apps.get_model("products", "VatRate")
    VatRate.objects.filter(code="VAT14").update(code="VAT16")


class Migration(migrations.Migration):

    dependencies = [
        ("products", "0011_vat16_to_14"),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
