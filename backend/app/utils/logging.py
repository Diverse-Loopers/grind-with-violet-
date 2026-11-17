"""
Secure structured logging that never prints sensitive tokens.
"""

from __future__ import annotations

import logging
import re
import sys
from datetime import datetime, timezone


_SENSITIVE_PATTERNS = [
    re.compile(r"(Bearer\s+)\S+", re.IGNORECASE),
    re.compile(r"(token[\"']?\s*[:=]\s*[\"']?)\S+", re.IGNORECASE),
    re.compile(r"(api_key[\"']?\s*[:=]\s*[\"']?)\S+", re.IGNORECASE),
    re.compile(r"(password[\"']?\s*[:=]\s*[\"']?)\S+", re.IGNORECASE),
    re.compile(r"(Authorization[\"']?\s*[:=]\s*[\"']?)\S+", re.IGNORECASE),
]


class SecureFormatter(logging.Formatter):
    """Formatter that redacts sensitive information from log messages."""

    def format(self, record: logging.LogRecord) -> str:
        message = super().format(record)
        for pattern in _SENSITIVE_PATTERNS:
            message = pattern.sub(r"\1***REDACTED***", message)
        return message


def get_logger(name: str, level: int = logging.INFO) -> logging.Logger:
    """
    Create a structured logger with secure formatting.

    Args:
        name: Logger name (typically __name__).
        level: Logging level.

    Returns:
        Configured logger instance.
    """
    logger = logging.getLogger(name)

    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(level)

        fmt = SecureFormatter(
            fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S%z",
        )
        handler.setFormatter(fmt)
        logger.addHandler(handler)

    logger.setLevel(level)
    logger.propagate = False
    return logger


logger = get_logger("groww")


def utc_now_str() -> str:
    """Return current UTC timestamp as ISO string."""
    return datetime.now(timezone.utc).isoformat()
