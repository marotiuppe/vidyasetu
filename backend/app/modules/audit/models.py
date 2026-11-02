from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, utcnow


class AuditLog(Base):
    """Append-only record of who did what. Rows are never updated or deleted.

    School, branch and actor are plain integers (no foreign keys) so the trail outlives the rows
    it points to. `detail` holds non-personal facts only, never names, contact details, secrets or
    setting values.
    """

    __tablename__ = "audit_log"
    __table_args__ = (
        Index("ix_audit_log_school_at", "school_id", "at"),
        Index("ix_audit_log_branch_at", "branch_id", "at"),
        Index("ix_audit_log_actor_at", "actor_user_id", "at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    school_id: Mapped[int | None] = mapped_column(Integer)
    branch_id: Mapped[int | None] = mapped_column(Integer)
    actor_user_id: Mapped[int | None] = mapped_column(Integer)
    actor_role: Mapped[str | None] = mapped_column(String(20))
    action: Mapped[str] = mapped_column(String(50), index=True)
    entity_type: Mapped[str | None] = mapped_column(String(30))
    entity_id: Mapped[str | None] = mapped_column(String(40))
    outcome: Mapped[str] = mapped_column(String(10), default="ok")
    ip: Mapped[str | None] = mapped_column(String(64))
    request_id: Mapped[str | None] = mapped_column(String(40))
    detail: Mapped[dict[str, Any] | None] = mapped_column(JSON)
