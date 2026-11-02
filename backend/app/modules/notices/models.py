import enum
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, utcnow


class TargetType(enum.StrEnum):
    SCHOOL = "school"
    BRANCH = "branch"
    CLASS = "class"
    SECTION = "section"


class NoticeCategory(enum.StrEnum):
    GENERAL = "general"
    ACADEMIC = "academic"
    EVENT = "event"
    HOLIDAY = "holiday"
    URGENT = "urgent"


def _enum(e: type[enum.StrEnum], length: int = 20) -> Enum:
    return Enum(e, native_enum=False, length=length, values_callable=lambda x: [m.value for m in x])


class Notice(TimestampMixin, Base):
    """A notice/circular aimed at the whole school, a branch, a class or a section."""

    __tablename__ = "notices"
    __table_args__ = (
        Index("ix_notices_school_branch", "school_id", "branch_id"),
        ForeignKeyConstraint(["branch_id", "school_id"], ["branches.id", "branches.school_id"]),
        ForeignKeyConstraint(["class_id", "branch_id"], ["classes.id", "classes.branch_id"]),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    school_id: Mapped[int] = mapped_column(index=True)
    branch_id: Mapped[int | None] = mapped_column()
    class_id: Mapped[int | None] = mapped_column(index=True)
    section_id: Mapped[int | None] = mapped_column(ForeignKey("sections.id"), index=True)
    target_type: Mapped[TargetType] = mapped_column(_enum(TargetType))
    title: Mapped[str] = mapped_column(String(150))
    body: Mapped[str] = mapped_column(Text)
    category: Mapped[NoticeCategory] = mapped_column(
        _enum(NoticeCategory), default=NoticeCategory.GENERAL
    )
    is_pinned: Mapped[bool] = mapped_column(Boolean, default=False)
    expires_on: Mapped[date | None] = mapped_column(Date)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)


class NoticeRead(Base):
    """Marks that a user has read a notice."""

    __tablename__ = "notice_reads"
    __table_args__ = (UniqueConstraint("notice_id", "user_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    notice_id: Mapped[int] = mapped_column(ForeignKey("notices.id", ondelete="CASCADE"))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    read_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
