from datetime import date

from sqlalchemy import (
    Boolean,
    Date,
    ForeignKey,
    ForeignKeyConstraint,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class AcademicYear(TimestampMixin, Base):
    """School-wide academic year (the year starts in April)."""

    __tablename__ = "academic_years"
    __table_args__ = (UniqueConstraint("school_id", "name"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    school_id: Mapped[int] = mapped_column(ForeignKey("schools.id"), index=True)
    name: Mapped[str] = mapped_column(String(20))  # e.g. "2026-27"
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date)
    is_current: Mapped[bool] = mapped_column(Boolean, default=False)


class SchoolClass(TimestampMixin, Base):
    """A class/standard of one branch (e.g. 1st, 2nd ... 10th)."""

    __tablename__ = "classes"
    __table_args__ = (
        UniqueConstraint("branch_id", "level"),
        UniqueConstraint("id", "branch_id"),
        ForeignKeyConstraint(["branch_id", "school_id"], ["branches.id", "branches.school_id"]),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    school_id: Mapped[int] = mapped_column(index=True)
    branch_id: Mapped[int] = mapped_column(index=True)
    name: Mapped[str] = mapped_column(String(50))
    level: Mapped[int] = mapped_column()  # 1..10, used for ordering and promotion


class Section(TimestampMixin, Base):
    """A division of a class (e.g. A, B)."""

    __tablename__ = "sections"
    __table_args__ = (
        UniqueConstraint("class_id", "name"),
        ForeignKeyConstraint(["class_id", "branch_id"], ["classes.id", "classes.branch_id"]),
        ForeignKeyConstraint(["branch_id", "school_id"], ["branches.id", "branches.school_id"]),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    school_id: Mapped[int] = mapped_column(index=True)
    branch_id: Mapped[int] = mapped_column(index=True)
    class_id: Mapped[int] = mapped_column(index=True)
    name: Mapped[str] = mapped_column(String(20))
