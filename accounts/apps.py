from django.apps import AppConfig
from django.db.models.signals import post_migrate


class AccountsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "accounts"

    def ready(self):
        from .groups import ensure_warehouse_groups

        post_migrate.connect(
            ensure_warehouse_groups,
            dispatch_uid="accounts.ensure_warehouse_groups",
        )
