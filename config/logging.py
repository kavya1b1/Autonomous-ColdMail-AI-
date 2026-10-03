"""Structured logging configuration"""
import logging
import sys
from pathlib import Path
from datetime import datetime

from config.settings import settings


def setup_logging() -> logging.Logger:
    """Configure structured logging"""

    logger = logging.getLogger("coldmail")
    logger.setLevel(getattr(logging, settings.LOG_LEVEL.upper()))

    # Clear existing handlers
    logger.handlers = []

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG)

    # Format
    if settings.LOG_FORMAT == "json":
        formatter = logging.Formatter(
            '{{"timestamp": "%(asctime)s", "level": "%(levelname)s", "logger": "%(name)s", "message": "%(message)s", "module": "%(module)s", "function": "%(funcName)s"}}'
        )
    else:
        formatter = logging.Formatter(
            '%(asctime)s | %(levelname)-8s | %(name)s | %(module)s:%(funcName)s | %(message)s'
        )

    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # File handler
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    file_handler = logging.FileHandler(
        log_dir / f"coldmail_{datetime.now().strftime('%Y%m%d')}.log"
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger


logger = setup_logging()
