from django.apps import AppConfig


class LoggingUtilsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "logging_utils"
    verbose_name = "Logging utilities"

    def ready(self):
        from logging_utils.logging_config import configure_django_loggers

        configure_django_loggers()
