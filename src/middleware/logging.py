"""Structured logging configuration."""

import logging
import sys
from typing import Any, Dict


def setup_logging(log_level: str = "INFO") -> None:
    """Configure structured logging."""
    # Set up root logger
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )

    # Set exchangelib to WARNING to reduce noise
    logging.getLogger("exchangelib").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)


class AuditLogger:
    """Audit logger for tracking operations."""

    def __init__(self):
        self.logger = logging.getLogger("audit")

    def log_operation(
        self,
        operation: str,
        user: str,
        success: bool,
        details: Dict[str, Any] = None
    ) -> None:
        """Log an operation for audit trail."""
        message = f"Operation: {operation} | User: {user} | Success: {success}"
        if details:
            message += f" | Details: {details}"

        if success:
            self.logger.info(message)
        else:
            self.logger.warning(message)
