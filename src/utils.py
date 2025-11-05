"""Utility functions for EWS MCP Server."""

from datetime import datetime
from typing import Any, Dict, Optional
import logging
import os
from exchangelib import EWSTimeZone, EWSDateTime
import pytz


def get_timezone():
    """Get the configured timezone as EWSTimeZone."""
    # Get timezone from environment or default to UTC
    tz_name = os.environ.get('TIMEZONE', os.environ.get('TZ', 'UTC'))
    try:
        return EWSTimeZone(tz_name)
    except Exception:
        # Fallback to UTC if timezone not found
        return EWSTimeZone('UTC')


def get_pytz_timezone():
    """Get the configured timezone as pytz timezone."""
    tz_name = os.environ.get('TIMEZONE', os.environ.get('TZ', 'UTC'))
    try:
        return pytz.timezone(tz_name)
    except Exception:
        return pytz.UTC


def make_tz_aware(dt: datetime) -> EWSDateTime:
    """Make a naive datetime timezone-aware as EWSDateTime with EWSTimeZone.

    This is the correct way to create datetime objects for exchangelib.
    """
    if isinstance(dt, EWSDateTime):
        # Already EWSDateTime
        return dt

    tz = get_timezone()

    if dt.tzinfo is not None:
        # Already timezone-aware - convert to target timezone first
        # Get the target timezone as pytz for conversion
        tz_name = os.environ.get('TIMEZONE', os.environ.get('TZ', 'UTC'))
        target_tz = pytz.timezone(tz_name)

        # Convert to target timezone
        dt_converted = dt.astimezone(target_tz)

        # Create EWSDateTime with EWSTimeZone
        return EWSDateTime(
            dt_converted.year, dt_converted.month, dt_converted.day,
            dt_converted.hour, dt_converted.minute, dt_converted.second,
            dt_converted.microsecond,
            tzinfo=tz
        )

    # Naive datetime - create EWSDateTime with configured timezone
    return EWSDateTime(
        dt.year, dt.month, dt.day,
        dt.hour, dt.minute, dt.second,
        dt.microsecond,
        tzinfo=tz
    )


def parse_datetime_tz_aware(dt_str: str) -> EWSDateTime:
    """Parse ISO 8601 datetime string and return as EWSDateTime with EWSTimeZone.

    This ensures all datetime objects used with exchangelib have the correct timezone format.
    """
    if not dt_str:
        return None

    try:
        # Parse the datetime string
        dt = datetime.fromisoformat(dt_str.replace('Z', '+00:00'))

        # Convert to EWSDateTime with configured timezone
        return make_tz_aware(dt)
    except ValueError:
        return None


def format_datetime(dt: Optional[datetime]) -> Optional[str]:
    """Format datetime to ISO 8601 string."""
    if dt is None:
        return None
    return dt.isoformat()


def parse_datetime(dt_str: Optional[str]) -> Optional[datetime]:
    """Parse ISO 8601 datetime string (legacy - use parse_datetime_tz_aware instead)."""
    if not dt_str:
        return None
    try:
        return datetime.fromisoformat(dt_str.replace('Z', '+00:00'))
    except ValueError:
        return None


def sanitize_html(html: str) -> str:
    """Basic HTML sanitization."""
    # In production, use a proper HTML sanitizer like bleach
    return html


def truncate_text(text: str, max_length: int = 100) -> str:
    """Truncate text to max length."""
    if len(text) <= max_length:
        return text
    return text[:max_length - 3] + "..."


def safe_get(obj: Any, attr: str, default: Any = None) -> Any:
    """Safely get attribute from object."""
    try:
        return getattr(obj, attr, default)
    except Exception:
        return default


def format_error_response(error: Exception, context: str = "") -> Dict[str, Any]:
    """Format error as response dictionary."""
    logger = logging.getLogger(__name__)
    error_msg = f"{context}: {str(error)}" if context else str(error)
    logger.error(error_msg)

    return {
        "success": False,
        "message": error_msg,
        "error_type": type(error).__name__
    }


def format_success_response(message: str, **kwargs) -> Dict[str, Any]:
    """Format success response."""
    response = {
        "success": True,
        "message": message
    }
    response.update(kwargs)
    return response
