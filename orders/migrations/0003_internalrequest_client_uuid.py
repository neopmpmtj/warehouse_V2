import uuid

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0002_line_quantity_reserved"),
    ]

    operations = [
        migrations.AddField(
            model_name="internalrequest",
            name="client_uuid",
            field=models.UUIDField(blank=True, db_index=True, null=True, unique=True),
        ),
    ]
