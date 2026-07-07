# -*- coding: utf-8 -*-
"""Structured logging for OAK Trading system."""
import logging
import os
from logging.handlers import RotatingFileHandler

LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
LOG_FORMAT = "%(asctime)s [%(name)s] %(levelname)s - %(message)s"


def setup_logger(name, level=logging.INFO):
    """Create a logger with console + rotating file handlers."""
    os.makedirs(LOG_DIR, exist_ok=True)
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger  # Already configured
    logger.setLevel(level)

    # Console handler
    ch = logging.StreamHandler()
    ch.setFormatter(logging.Formatter(LOG_FORMAT))
    logger.addHandler(ch)

    # File handler (10MB, 5 backups)
    log_file = os.path.join(LOG_DIR, "app.log")
    fh = RotatingFileHandler(log_file, maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8")
    fh.setFormatter(logging.Formatter(LOG_FORMAT))
    logger.addHandler(fh)

    return logger
