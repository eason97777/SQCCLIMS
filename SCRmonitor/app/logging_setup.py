"""Logging configuration for the SCRmonitor backend.

``setup_logging()`` wires Python's stdlib ``logging`` to a rotating file in
``config.LOG_DIR`` plus stderr. It is read from ``config.LOG_DIR`` at call
time because the path is reassigned by ``configure_paths()`` at startup, so
this module must be set up AFTER paths are configured.
"""
import logging
from logging.handlers import RotatingFileHandler

import app.config as config

LOGGER_NAME = "scrmonitor"

logger = logging.getLogger(LOGGER_NAME)

_LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s %(message)s"

# Marker so we can detect handlers we already installed and stay idempotent.
_MANAGED_ATTR = "_scrmonitor_managed"


def get_logger(name=None):
    """Return the package logger, or a child logger when ``name`` is given."""
    if name:
        return logging.getLogger(f"{LOGGER_NAME}.{name}")
    return logger


def _has_managed_handler(target, kind):
    for handler in target.handlers:
        if getattr(handler, _MANAGED_ATTR, None) == kind:
            return True
    return False


def setup_logging(level=logging.INFO):
    """Configure the ``scrmonitor`` logger with rotating-file + stderr output.

    Idempotent: repeated calls do not add duplicate handlers. ``config.LOG_DIR``
    is read at call time and created if missing.
    """
    logger.setLevel(level)
    # Keep our records on our own handlers only; the root logger may have its
    # own configuration we do not want to duplicate into.
    logger.propagate = False

    formatter = logging.Formatter(_LOG_FORMAT)

    if not _has_managed_handler(logger, "stream"):
        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(formatter)
        setattr(stream_handler, _MANAGED_ATTR, "stream")
        logger.addHandler(stream_handler)

    if not _has_managed_handler(logger, "file"):
        log_dir = config.LOG_DIR
        log_dir.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(
            log_dir / "app.log",
            maxBytes=5 * 1024 * 1024,
            backupCount=5,
            encoding="utf-8",
        )
        file_handler.setFormatter(formatter)
        setattr(file_handler, _MANAGED_ATTR, "file")
        logger.addHandler(file_handler)

    return logger
