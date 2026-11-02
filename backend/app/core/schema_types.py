"""Shared field types for API schemas.

Timestamps are stored in UTC. SQLite returns them without a time zone and the JSON output must not
be ambiguous, so every datetime leaving the API carries an explicit UTC offset ("Z").
Use `UtcDateTime` for any datetime field in a response schema.
"""

from datetime import UTC, datetime
from typing import Annotated

from pydantic import PlainSerializer

from app.db.base import as_utc


def _to_utc(value: datetime) -> datetime:
    return as_utc(value).astimezone(UTC)


UtcDateTime = Annotated[datetime, PlainSerializer(_to_utc, when_used="json")]


def utc_iso(value: datetime | None) -> str | None:
    """ISO 8601 text in UTC with an explicit offset, for hand-built output (CSV, files)."""
    if value is None:
        return None
    return as_utc(value).isoformat()
