"""Structured Logger - Phase 1"""
import json
import logging
from datetime import datetime
from typing import Any


class StructuredLogger:
    """JSON structured logger (Phase 1)"""

    LOG_LEVELS = {
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "WARN": logging.WARNING,
        "ERROR": logging.ERROR,
        "CRITICAL": logging.CRITICAL,
    }

    def __init__(self, service: str = "omnibot"):
        self.service = service
        self.logger = logging.getLogger(service)

    def log(self, level: str, message: str, **kwargs: Any) -> None:
        entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": level,
            "service": self.service,
            "message": message,
            **kwargs,
        }
        self.logger.log(self.LOG_LEVELS.get(level, logging.INFO), json.dumps(entry))

    def info(self, message: str, **kwargs: Any) -> None:
        self.log("INFO", message, **kwargs)

    def error(self, message: str, **kwargs: Any) -> None:
        self.log("ERROR", message, **kwargs)

    def warn(self, message: str, **kwargs: Any) -> None:
        self.log("WARN", message, **kwargs)
