"""
Production-level logging and monitoring.
"""
import logging
import sys
import json
from typing import Optional
from datetime import datetime

import structlog
from pythonjsonlogger import jsonlogger

# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)


def setup_logging(
    level: str = "INFO",
    log_file: Optional[str] = None,
    json_logs: bool = True
) -> None:
    """Setup application logging with proper formatting."""
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(level.upper())

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level.upper())

    if json_logs:
        # JSON formatter for structured logging
        formatter = jsonlogger.JsonFormatter()
        console_handler.setFormatter(formatter)
    else:
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        console_handler.setFormatter(formatter)

    root_logger.addHandler(console_handler)

    # File handler if specified
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(level.upper())

        if json_logs:
            formatter = jsonlogger.JsonFormatter()
            file_handler.setFormatter(formatter)
        else:
            formatter = logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            )
            file_handler.setFormatter(formatter)

        root_logger.addHandler(file_handler)


class AppLogger:
    """Application-specific logging wrapper."""

    def __init__(self, name: str):
        self.logger = structlog.get_logger(name)

    def info(self, message: str, **kwargs):
        """Log info level message."""
        self.logger.info(message, **kwargs)

    def warning(self, message: str, **kwargs):
        """Log warning level message."""
        self.logger.warning(message, **kwargs)

    def error(self, message: str, exc_info: bool = False, **kwargs):
        """Log error level message."""
        self.logger.error(message, exc_info=exc_info, **kwargs)

    def debug(self, message: str, **kwargs):
        """Log debug level message."""
        self.logger.debug(message, **kwargs)

    def critical(self, message: str, **kwargs):
        """Log critical level message."""
        self.logger.critical(message, **kwargs)

    def log_event(self, event_type: str, details: dict):
        """Log a structured event."""
        self.logger.info("event", event_type=event_type, **details)

    def log_error(self, error_type: str, message: str, traceback_str: Optional[str] = None):
        """Log error with type and optional traceback."""
        self.logger.error(
            "error_occurred",
            error_type=error_type,
            message=message,
            traceback=traceback_str
        )

    def log_performance(self, operation: str, duration_ms: float, success: bool):
        """Log performance metrics."""
        self.logger.info(
            "operation_completed",
            operation=operation,
            duration_ms=duration_ms,
            success=success
        )


def get_logger(name: str) -> AppLogger:
    """Get an application logger."""
    return AppLogger(name)
