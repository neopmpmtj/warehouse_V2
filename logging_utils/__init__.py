"""
Centralized logging for CentCompras.

Usage:
    from logging_utils import get_logger

    logger = get_logger("centcompras.products")
    logger.info("Catalogue loaded")
"""

from .logging_config import (
    DEFAULT_DATE_FORMAT,
    DEFAULT_LOG_DIR,
    DEFAULT_LOG_FORMAT,
    LOGGING_CONFIG,
    configure_django_loggers,
    get_logger,
    set_console_level,
)

__all__ = [
    "configure_django_loggers",
    "get_logger",
    "set_console_level",
    "LOGGING_CONFIG",
    "DEFAULT_LOG_DIR",
    "DEFAULT_LOG_FORMAT",
    "DEFAULT_DATE_FORMAT",
]
