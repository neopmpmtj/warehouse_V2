"""
Centralized logging configuration for CentCompras.

Provides per-module loggers with console and rotating file output.
"""

import logging
import logging.handlers
import sys
import warnings
from pathlib import Path
from typing import Optional

try:
    from concurrent_log_handler import (
        ConcurrentRotatingFileHandler as RotatingFileHandler,
    )
except ImportError:  # pragma: no cover - single-process fallback
    RotatingFileHandler = logging.handlers.RotatingFileHandler

LOGGING_CONFIG = {
    "defaults": {
        "console_level": "DEBUG",
        "file_level": "DEBUG",
        "console_output": True,
        "file_output": True,
        "rotation": {
            "mode": "size",
            "max_bytes": 10 * 1024 * 1024,
            "backup_count": 7,
        },
    },
    "loggers": {
        "centcompras": {
            "log_filename": "centcompras.log",
        },
        "centcompras.accounts": {
            "log_filename": "accounts.log",
        },
        "centcompras.products": {
            "log_filename": "products.log",
        },
        "centcompras.procurement": {
            "log_filename": "procurement.log",
        },
        "centcompras.inventory": {
            "log_filename": "inventory.log",
        },
        "centcompras.branches": {
            "log_filename": "branches.log",
        },
        "centcompras.orders": {
            "log_filename": "orders.log",
        },
        "centcompras.threads": {
            "log_filename": "threads.log",
        },
        "centcompras.django": {
            "log_filename": "django.log",
            "console_level": "INFO",
        },
    },
    "strict_config": False,
}

DEFAULT_LOG_DIR = "logs"
DEFAULT_LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
DEFAULT_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def get_project_base_dir() -> Path:
    try:
        from django.conf import settings

        if settings.configured:
            return Path(settings.BASE_DIR)
    except ImportError:
        pass

    return Path(__file__).resolve().parent.parent


def determine_log_dir(base_dir: Optional[Path] = None) -> Path:
    if base_dir is None:
        return get_project_base_dir() / DEFAULT_LOG_DIR
    return Path(base_dir)


def create_rotating_file_handler(
    log_path: Path,
    level: str,
    max_bytes: int,
    backup_count: int,
) -> logging.Handler:
    log_path.parent.mkdir(parents=True, exist_ok=True)

    # RotatingFileHandler is ConcurrentRotatingFileHandler when the optional
    # dependency is installed, which keeps rotation safe under multi-process WSGI.
    handler = RotatingFileHandler(
        log_path,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8",
    )
    handler.setLevel(getattr(logging, level.upper()))
    return handler


def set_console_level(logger: logging.Logger, level: str) -> None:
    level_upper = level.upper()
    log_level = getattr(logging, level_upper)

    for handler in logger.handlers:
        if isinstance(handler, logging.StreamHandler) and not isinstance(
            handler, logging.FileHandler
        ):
            handler.setLevel(log_level)


def _is_testing() -> bool:
    try:
        from django.conf import settings

        if settings.configured:
            return bool(getattr(settings, "TESTING", False))
    except Exception:  # pragma: no cover
        pass
    return False


def get_logger(
    logger_name: str,
    log_dir: Optional[Path] = None,
    console_level: Optional[str] = None,
    file_level: Optional[str] = None,
) -> logging.Logger:
    defaults = LOGGING_CONFIG.get("defaults", {})
    logger_config = LOGGING_CONFIG.get("loggers", {}).get(logger_name, {})
    strict_config = LOGGING_CONFIG.get("strict_config", False)

    if strict_config and logger_name not in LOGGING_CONFIG.get("loggers", {}):
        raise ValueError(
            f"Logger '{logger_name}' not found in configuration and strict_config is enabled"
        )

    if not strict_config and logger_name not in LOGGING_CONFIG.get("loggers", {}):
        if not hasattr(get_logger, "_warned_loggers"):
            get_logger._warned_loggers = set()

        if logger_name not in get_logger._warned_loggers:
            warnings.warn(
                f"Logger '{logger_name}' not in configuration, using defaults",
                stacklevel=2,
            )
            get_logger._warned_loggers.add(logger_name)

    config = {**defaults, **logger_config}

    testing = _is_testing()
    if testing:
        # Under the test runner, keep logs quiet and skip disk writes entirely.
        config["console_level"] = "WARNING"
        config["file_level"] = "WARNING"
        config["file_output"] = False

    if console_level is not None:
        config["console_level"] = console_level
    if file_level is not None:
        config["file_level"] = file_level
    if log_dir is not None:
        config["log_dir"] = log_dir

    logger = logging.getLogger(logger_name)

    if not logger.handlers:
        logger.setLevel(logging.WARNING if testing else logging.DEBUG)
        logger.propagate = False

        formatter = logging.Formatter(
            fmt=DEFAULT_LOG_FORMAT,
            datefmt=DEFAULT_DATE_FORMAT,
        )

        if config.get("console_output", True):
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setLevel(getattr(logging, config["console_level"].upper()))
            console_handler.setFormatter(formatter)
            logger.addHandler(console_handler)

        if config.get("file_output", True):
            resolved_log_dir = determine_log_dir(config.get("log_dir"))
            log_filename = config.get("log_filename", f"{logger_name}.log")
            log_file = resolved_log_dir / log_filename

            rotation = config.get("rotation", {})
            max_bytes = rotation.get("max_bytes", 10 * 1024 * 1024)
            backup_count = rotation.get("backup_count", 7)

            file_handler = create_rotating_file_handler(
                log_file,
                config["file_level"],
                max_bytes,
                backup_count,
            )
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)

    return logger


def configure_django_loggers() -> None:
    """Route Django request/server loggers through centcompras file handlers."""
    django_logger = get_logger("centcompras.django")

    for name in ("django.request", "django.server"):
        logger = logging.getLogger(name)
        if logger.handlers:
            continue
        for handler in django_logger.handlers:
            logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        logger.propagate = False
