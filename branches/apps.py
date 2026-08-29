from django.apps import AppConfig
from django.db.models.signals import post_migrate


class BranchesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "branches"

    def ready(self):
        def _ensure(sender, **kwargs):
            if getattr(sender, "name", None) != "branches":
                return
            from .services import ensure_default_commercial_settings

            ensure_default_commercial_settings()

        post_migrate.connect(
            _ensure,
            dispatch_uid="branches.ensure_default_commercial_settings",
        )
