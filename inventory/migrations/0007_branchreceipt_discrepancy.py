from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("inventory", "0006_integer_quantities"),
    ]

    operations = [
        migrations.AddField(
            model_name="branchreceipt",
            name="discrepancy_reason",
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name="branchreceipt",
            name="is_critical",
            field=models.BooleanField(db_index=True, default=False),
        ),
        migrations.AddField(
            model_name="branchreceiptline",
            name="quantity_written_off",
            field=models.IntegerField(default=0),
        ),
        migrations.AddConstraint(
            model_name="branchreceiptline",
            constraint=models.CheckConstraint(
                condition=models.Q(quantity_received__gte=0),
                name="branch_receipt_line_received_gte_zero",
            ),
        ),
        migrations.AddConstraint(
            model_name="branchreceiptline",
            constraint=models.CheckConstraint(
                condition=models.Q(quantity_written_off__gte=0),
                name="branch_receipt_line_written_off_gte_zero",
            ),
        ),
    ]
