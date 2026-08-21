from django.apps import AppConfig
from django.db.models.signals import post_migrate


class ProcurementConfig(AppConfig):
    default = True
    name = "procurement"

    def ready(self):
        def _ensure(sender, **kwargs):
            if getattr(sender, "name", None) != "procurement":
                return
            from .services import ensure_default_approval_limits

            ensure_default_approval_limits()

        post_migrate.connect(
            _ensure,
            dispatch_uid="procurement.ensure_default_approval_limits",
        )
