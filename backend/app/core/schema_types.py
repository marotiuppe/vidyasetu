"""Shared field types for API schemas.

Timestamps are stored in UTC. SQLite returns them without a time zone and the JSON output must not
be ambiguous, so every datetime leaving the API carries an explicit UTC offset ("Z").
Use `UtcDateTime` for any datetime field in a response schema.
"""

from datetime import UTC, datetime
from typing import Annotated

from pydantic import BaseModel, PlainSerializer, ValidationError

from app.db.base import as_utc


def _to_utc(value: datetime) -> datetime:
    return as_utc(value).astimezone(UTC)


UtcDateTime = Annotated[datetime, PlainSerializer(_to_utc, when_used="json")]


def utc_iso(value: datetime | None) -> str | None:
    """ISO 8601 text in UTC with an explicit offset, for hand-built output (CSV, files)."""
    if value is None:
        return None
    return as_utc(value).isoformat()


class RowRejected(Exception):
    """An import row refused with a user-safe message (its text becomes the row error)."""


class ImportRowError(BaseModel):
    """One rejected row of a CSV or bulk import: its 1-based number and a user-safe message."""

    row: int
    message: str


def validation_message(exc: ValidationError) -> str:
    """Field errors as one line. Only locations and messages, never the submitted values."""
    parts = []
    for err in exc.errors():
        loc = ".".join(str(p) for p in err["loc"])
        msg = err["msg"].removeprefix("Value error, ")
        parts.append(f"{loc}: {msg}" if loc else msg)
    return "; ".join(parts)
