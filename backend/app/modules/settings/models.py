from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, utcnow


class Setting(Base):
    """A stored value for a platform, school or branch setting.

    `scope` is "platform", "s:<school_id>" or "b:<branch_id>". It makes (scope, key) unique on
    every database, which a unique index over nullable school/branch columns would not.
    """

    __tablename__ = "settings"
    __table_args__ = (
        UniqueConstraint("scope", "key", name="uq_settings_scope_key"),
        Index("ix_settings_school_id", "school_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    level: Mapped[str] = mapped_column(String(10))
    school_id: Mapped[int | None] = mapped_column(ForeignKey("schools.id", ondelete="CASCADE"))
    branch_id: Mapped[int | None] = mapped_column(ForeignKey("branches.id", ondelete="CASCADE"))
    scope: Mapped[str] = mapped_column(String(30))
    key: Mapped[str] = mapped_column(String(100))
    # Secrets hold the Fernet token (a string) here, never the plain value.
    value: Mapped[Any] = mapped_column(JSON)
    is_secret: Mapped[bool] = mapped_column(Boolean, default=False)
    updated_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class UserPreference(Base):
    """A personal setting. Only its owner reads or writes it."""

    __tablename__ = "user_preferences"
    __table_args__ = (UniqueConstraint("user_id", "key", name="uq_user_preferences_user_key"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    key: Mapped[str] = mapped_column(String(100))
    value: Mapped[Any] = mapped_column(JSON)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )
