import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("inventory", "0007_branchreceipt_discrepancy"),
        ("orders", "0004_integer_quantities"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="branchreceipt",
            name="follow_up_request",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="source_receipts",
                to="orders.internalrequest",
            ),
        ),
        migrations.CreateModel(
            name="BranchReceiptReadState",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("read_at", models.DateTimeField(auto_now=True)),
                (
                    "receipt",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="read_states",
                        to="inventory.branchreceipt",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="branch_receipt_read_states",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
        ),
        migrations.AddConstraint(
            model_name="branchreceiptreadstate",
            constraint=models.UniqueConstraint(
                fields=("receipt", "user"),
                name="unique_branch_receipt_read_state",
            ),
        ),
    ]
