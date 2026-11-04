"""Timetable: the period slots of a branch and the weekly entries of each section.

Every table carries school_id and branch_id. Links to sections, subjects and periods use composite
keys with branch_id, so a row cannot point across branches. The teacher is a user of the same
branch, checked by the service (users have no branch-level unique key to reference).
"""

from datetime import time

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Time,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class PeriodSlot(TimestampMixin, Base):
    """One slot of the school day of a branch (a period or a break)."""

    __tablename__ = "period_slots"
    __table_args__ = (
        UniqueConstraint("branch_id", "sequence"),
        UniqueConstraint("id", "branch_id"),
        ForeignKeyConstraint(["branch_id", "school_id"], ["branches.id", "branches.school_id"]),
        CheckConstraint("end_time > start_time", "ck_period_slots_times"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    school_id: Mapped[int] = mapped_column(index=True)
    branch_id: Mapped[int] = mapped_column(index=True)
    name: Mapped[str] = mapped_column(String(50))
    sequence: Mapped[int] = mapped_column(Integer)
    start_time: Mapped[time] = mapped_column(Time)
    end_time: Mapped[time] = mapped_column(Time)
    is_break: Mapped[bool] = mapped_column(Boolean, default=False)


class TimetableEntry(TimestampMixin, Base):
    """What a section has in one period on one weekday (1 = Monday ... 7 = Sunday)."""

    __tablename__ = "timetable_entries"
    __table_args__ = (
        UniqueConstraint("section_id", "academic_year_id", "weekday", "period_id"),
        ForeignKeyConstraint(["section_id", "branch_id"], ["sections.id", "sections.branch_id"]),
        ForeignKeyConstraint(
            ["period_id", "branch_id"], ["period_slots.id", "period_slots.branch_id"]
        ),
        ForeignKeyConstraint(["subject_id", "branch_id"], ["subjects.id", "subjects.branch_id"]),
        ForeignKeyConstraint(["branch_id", "school_id"], ["branches.id", "branches.school_id"]),
        CheckConstraint("weekday >= 1 AND weekday <= 7", "ck_timetable_entries_weekday"),
        Index(
            "ix_timetable_entries_teacher_slot",
            "teacher_id",
            "academic_year_id",
            "weekday",
            "period_id",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    school_id: Mapped[int] = mapped_column(index=True)
    branch_id: Mapped[int] = mapped_column(index=True)
    academic_year_id: Mapped[int] = mapped_column(ForeignKey("academic_years.id"), index=True)
    section_id: Mapped[int] = mapped_column(index=True)
    weekday: Mapped[int] = mapped_column(Integer)
    period_id: Mapped[int] = mapped_column(index=True)
    subject_id: Mapped[int] = mapped_column(index=True)
    teacher_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    room: Mapped[str | None] = mapped_column(String(30))
