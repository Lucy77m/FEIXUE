"""Centralized logging configuration for FEIXUE.

Called once at startup.  All modules then use ``logging.getLogger(__name__)``
to inherit the rotating-file handler configured here.
"""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path


def setup_logging(log_dir: Path, level: int = logging.WARNING) -> None:
    """Configure the ``desktop_pet`` logger with a rotating file handler.

    Parameters
    ----------
    log_dir:
        Directory for ``feixue.log`` (created if missing).
    level:
        Minimum severity captured.  Default ``WARNING`` keeps the log quiet
        during normal operation; switch to ``DEBUG`` to see full tracebacks
        from ``logger.debug(..., exc_info=True)`` calls.
    """
    log_dir.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(
        log_dir / "feixue.log",
        maxBytes=512 * 1024,   # 512 KB per file
        backupCount=3,          # keep 3 rotated files → max ~1.5 MB
        encoding="utf-8",
    )
    handler.setFormatter(logging.Formatter(
        "%(asctime)s %(levelname)s [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    ))
    root = logging.getLogger("desktop_pet")
    root.setLevel(level)
    root.addHandler(handler)
