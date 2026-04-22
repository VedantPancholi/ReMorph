"""Application logging helpers."""

import logging

from app.config import get_settings


def get_logger(name: str) -> logging.Logger:
    """Return a logger configured with the project log level."""

    settings = get_settings()
    logging.basicConfig(
        level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
    return logging.getLogger(name)
