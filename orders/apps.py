from django.apps import AppConfig
from django.db.models.signals import post_migrate


class OrdersConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "orders"

    def ready(self):
        def _ensure(sender, **kwargs):
            if getattr(sender, "name", None) != "orders":
                return
            from .services import ensure_default_branch_approval_limits

            ensure_default_branch_approval_limits()

        post_migrate.connect(
            _ensure,
            dispatch_uid="orders.ensure_default_branch_approval_limits",
        )
