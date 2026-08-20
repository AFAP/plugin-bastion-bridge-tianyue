"""
Centralized logging configuration for TianYue SSH Bridge.

Logs are written to the user's local application data directory so the tool
works reliably when packaged as a single-file Windows EXE and launched from
arbitrary working directories.
"""

import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional


#: Name of the application; used for the log directory and logger names.
APP_NAME = "TianYueSSHBridge"


def get_app_dir() -> Path:
    """Return the application data directory under ``%LOCALAPPDATA%``.

    All bridge applications share the same parent directory
    ``%LOCALAPPDATA%\sshbridge`` and are grouped by ``APP_NAME``.

    Falls back to a sibling ``.sshbridge`` directory in the user's home
    folder when ``LOCALAPPDATA`` is unavailable (e.g. some CI environments).
    """
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        return Path(local_app_data) / "sshbridge" / APP_NAME
    return Path.home() / ".sshbridge" / APP_NAME.lower()


def get_log_path() -> Path:
    """Return the full path to the rotating log file."""
    log_dir = get_app_dir() / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir / "bridge.log"


def get_config_path() -> Path:
    """Return the full path to the JSON configuration file."""
    config_dir = get_app_dir()
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir / "config.json"


def setup_logging(
    level: int = logging.DEBUG,
    max_bytes: int = 5 * 1024 * 1024,
    backup_count: int = 3,
    console: bool = True,
) -> logging.Logger:
    """Configure the root application logger.

    Args:
        level: Minimum log level (default ``logging.DEBUG``).
        max_bytes: Maximum size of ``bridge.log`` before rotation.
        backup_count: Number of rotated log files to keep.
        console: Also emit logs to ``stderr`` when ``True``. Useful during
            development; can be disabled for the packaged EXE to keep the
            console clean.

    Returns:
        The configured root logger for the application.
    """
    root_logger = logging.getLogger(APP_NAME)
    root_logger.setLevel(level)

    # Avoid duplicate handlers if setup_logging is called more than once.
    if root_logger.handlers:
        return root_logger

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Rotating file handler so the log directory does not grow unbounded.
    try:
        log_path = get_log_path()
        file_handler = RotatingFileHandler(
            filename=str(log_path),
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding="utf-8",
        )
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)
    except OSError as exc:
        # If we cannot write to the log file, at least complain on stderr.
        sys.stderr.write(f"[TianYueSSHBridge] Failed to open log file: {exc}\n")

    if console:
        console_handler = logging.StreamHandler(sys.stderr)
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)

    root_logger.info("Logging initialized. log_path=%s", get_log_path())
    return root_logger


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """Return a child logger under the application namespace."""
    full_name = APP_NAME if name is None else f"{APP_NAME}.{name}"
    return logging.getLogger(full_name)
