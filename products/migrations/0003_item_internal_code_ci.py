# Case-insensitive uniqueness for Item.internal_code.

import django.db.models.functions.text
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("products", "0002_seed_vat_rates"),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="item",
            name="unique_item_internal_code_when_set",
        ),
        migrations.AddConstraint(
            model_name="item",
            constraint=models.UniqueConstraint(
                django.db.models.functions.text.Lower("internal_code"),
                condition=models.Q(("internal_code", ""), _negated=True),
                name="unique_item_internal_code_ci",
            ),
        ),
    ]
