from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, LargeBinary, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, utcnow


class School(TimestampMixin, Base):
    """A tenant. Everything else belongs to exactly one school."""

    __tablename__ = "schools"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    code: Mapped[str] = mapped_column(String(50), unique=True)
    board: Mapped[str] = mapped_column(String(50), default="CBSE")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class SchoolLogo(Base):
    """A school's logo (normalised PNG). Kept apart so normal School queries never load the blob."""

    __tablename__ = "school_logos"

    school_id: Mapped[int] = mapped_column(
        ForeignKey("schools.id", ondelete="CASCADE"), primary_key=True
    )
    content_type: Mapped[str] = mapped_column(String(50), default="image/png")
    data: Mapped[bytes] = mapped_column(LargeBinary)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )
