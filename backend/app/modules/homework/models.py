"""Homework given to a section for a subject. No drafts and no attachments."""

from datetime import date

from sqlalchemy import (
    CheckConstraint,
    Date,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class Homework(TimestampMixin, Base):
    __tablename__ = "homework"
    __table_args__ = (
        ForeignKeyConstraint(["section_id", "branch_id"], ["sections.id", "sections.branch_id"]),
        ForeignKeyConstraint(["subject_id", "branch_id"], ["subjects.id", "subjects.branch_id"]),
        ForeignKeyConstraint(["branch_id", "school_id"], ["branches.id", "branches.school_id"]),
        CheckConstraint("due_date >= assigned_on", "ck_homework_dates"),
        Index("ix_homework_section_due", "section_id", "due_date"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    school_id: Mapped[int] = mapped_column(index=True)
    branch_id: Mapped[int] = mapped_column(index=True)
    academic_year_id: Mapped[int] = mapped_column(ForeignKey("academic_years.id"), index=True)
    section_id: Mapped[int] = mapped_column(index=True)
    subject_id: Mapped[int] = mapped_column(index=True)
    teacher_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    title: Mapped[str] = mapped_column(String(150))
    description: Mapped[str | None] = mapped_column(Text)
    assigned_on: Mapped[date] = mapped_column(Date)
    due_date: Mapped[date] = mapped_column(Date)
