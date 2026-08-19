import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models
from django.db.models.functions import Lower


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="VatRate",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("code", models.CharField(max_length=32, unique=True)),
                ("label", models.CharField(max_length=64)),
                ("rate", models.DecimalField(decimal_places=4, max_digits=5)),
            ],
            options={
                "ordering": ["rate"],
            },
        ),
        migrations.CreateModel(
            name="ProductFamily",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=255)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "ordering": ["name"],
            },
        ),
        migrations.CreateModel(
            name="Supplier",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=255)),
                ("contact_name", models.CharField(blank=True, max_length=255)),
                ("email", models.EmailField(blank=True, max_length=254)),
                ("phone", models.CharField(blank=True, max_length=64)),
                ("notes", models.TextField(blank=True)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "ordering": ["name"],
            },
        ),
        migrations.CreateModel(
            name="Item",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("internal_code", models.CharField(blank=True, max_length=64)),
                ("description", models.CharField(max_length=255)),
                ("unit_of_measure", models.CharField(
                    choices=[
                        ("piece", "Piece"),
                        ("kg", "Kilogram"),
                        ("g", "Gram"),
                        ("m", "Meter"),
                        ("m2", "Square meter"),
                        ("m3", "Cubic meter"),
                        ("l", "Liter"),
                    ],
                    default="piece",
                    max_length=16,
                )),
                ("reorder_level", models.DecimalField(decimal_places=3, default=0, max_digits=12)),
                ("is_active", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("family", models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="items",
                    to="products.productfamily",
                )),
                ("vat_rate", models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="items",
                    to="products.vatrate",
                )),
            ],
        ),
        migrations.CreateModel(
            name="FamilyChangeLog",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("action", models.CharField(
                    choices=[
                        ("created", "Created"),
                        ("updated", "Updated"),
                        ("deactivated", "Deactivated"),
                        ("reactivated", "Reactivated"),
                    ],
                    max_length=20,
                )),
                ("changes", models.JSONField(default=dict)),
                ("reason", models.CharField(blank=True, max_length=255)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("family", models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="change_logs",
                    to="products.productfamily",
                )),
                ("user", models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="family_change_logs",
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
        migrations.CreateModel(
            name="ItemChangeLog",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("action", models.CharField(
                    choices=[
                        ("created", "Created"),
                        ("updated", "Updated"),
                        ("deactivated", "Deactivated"),
                        ("reactivated", "Reactivated"),
                    ],
                    max_length=20,
                )),
                ("changes", models.JSONField(default=dict)),
                ("reason", models.CharField(blank=True, max_length=255)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("item", models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="change_logs",
                    to="products.item",
                )),
                ("user", models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="item_change_logs",
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
        migrations.CreateModel(
            name="SupplierChangeLog",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("action", models.CharField(
                    choices=[
                        ("created", "Created"),
                        ("updated", "Updated"),
                        ("deactivated", "Deactivated"),
                        ("reactivated", "Reactivated"),
                    ],
                    max_length=20,
                )),
                ("changes", models.JSONField(default=dict)),
                ("reason", models.CharField(blank=True, max_length=255)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("supplier", models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="change_logs",
                    to="products.supplier",
                )),
                ("user", models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="supplier_change_logs",
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
        migrations.AddConstraint(
            model_name="productfamily",
            constraint=models.UniqueConstraint(
                Lower("name"),
                name="unique_productfamily_name_ci",
            ),
        ),
        migrations.AddConstraint(
            model_name="supplier",
            constraint=models.UniqueConstraint(
                Lower("name"),
                name="unique_supplier_name_ci",
            ),
        ),
        migrations.AddConstraint(
            model_name="item",
            constraint=models.UniqueConstraint(
                condition=models.Q(("internal_code", ""), _negated=True),
                fields=("internal_code",),
                name="unique_item_internal_code_when_set",
            ),
        ),
    ]
