from django.db import migrations, models


def null_unrated_satisfaction(apps, schema_editor):
    Thread = apps.get_model("threads", "ItemRequestThread")
    Log = apps.get_model("threads", "ItemRequestThreadChangeLog")
    Thread.objects.exclude(status="closed").update(satisfaction=None)
    override_ids = list(
        Log.objects.filter(action="closed", changes__override=True).values_list(
            "thread_id", flat=True
        )
    )
    if override_ids:
        Thread.objects.filter(pk__in=override_ids).update(satisfaction=None)


class Migration(migrations.Migration):

    dependencies = [
        ("threads", "0002_itemrequestthread_satisfaction"),
    ]

    operations = [
        migrations.AlterField(
            model_name="itemrequestthread",
            name="satisfaction",
            field=models.PositiveSmallIntegerField(
                blank=True,
                choices=[
                    (1, "1 star"),
                    (2, "2 stars"),
                    (3, "3 stars"),
                    (4, "4 stars"),
                    (5, "5 stars"),
                ],
                help_text=(
                    "Opener's satisfaction (1–5 stars), set when the opener closes. "
                    "Null while the thread is open and on override close "
                    "(the closer must not rate for the opener)."
                ),
                null=True,
            ),
        ),
        migrations.RunPython(null_unrated_satisfaction, migrations.RunPython.noop),
    ]
