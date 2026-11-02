import enum
from datetime import date

from sqlalchemy import (
    Date,
    Enum,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class AttendanceStatus(enum.StrEnum):
    PRESENT = "present"
    ABSENT = "absent"
    LEAVE = "leave"


class StaffStatus(enum.StrEnum):
    PRESENT = "present"
    ABSENT = "absent"
    LEAVE = "leave"
    HALF_DAY = "half_day"


def _enum(e: type[enum.StrEnum], length: int = 20) -> Enum:
    return Enum(e, native_enum=False, length=length, values_callable=lambda x: [m.value for m in x])


class AttendanceRecord(TimestampMixin, Base):
    """One student's attendance for one day (a student has at most one record per date)."""

    __tablename__ = "attendance_records"
    __table_args__ = (
        UniqueConstraint("student_id", "date"),
        Index("ix_attendance_records_section_date", "section_id", "date"),
        Index("ix_attendance_records_branch_date", "branch_id", "date"),
        ForeignKeyConstraint(["student_id", "branch_id"], ["students.id", "students.branch_id"]),
        ForeignKeyConstraint(["class_id", "branch_id"], ["classes.id", "classes.branch_id"]),
        ForeignKeyConstraint(["branch_id", "school_id"], ["branches.id", "branches.school_id"]),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    school_id: Mapped[int] = mapped_column(index=True)
    branch_id: Mapped[int] = mapped_column()
    student_id: Mapped[int] = mapped_column()
    academic_year_id: Mapped[int] = mapped_column(ForeignKey("academic_years.id"), index=True)
    class_id: Mapped[int] = mapped_column()
    section_id: Mapped[int] = mapped_column(ForeignKey("sections.id"))
    date: Mapped[date] = mapped_column(Date)
    status: Mapped[AttendanceStatus] = mapped_column(_enum(AttendanceStatus))
    remark: Mapped[str | None] = mapped_column(String(200))
    marked_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    updated_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))


class StaffAttendance(TimestampMixin, Base):
    """One staff member's attendance for one day."""

    __tablename__ = "staff_attendance"
    __table_args__ = (
        UniqueConstraint("user_id", "date"),
        Index("ix_staff_attendance_branch_date", "branch_id", "date"),
        ForeignKeyConstraint(["branch_id", "school_id"], ["branches.id", "branches.school_id"]),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    school_id: Mapped[int] = mapped_column(index=True)
    branch_id: Mapped[int] = mapped_column()
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    date: Mapped[date] = mapped_column(Date)
    status: Mapped[StaffStatus] = mapped_column(_enum(StaffStatus))
    remark: Mapped[str | None] = mapped_column(String(200))
    marked_by: Mapped[int] = mapped_column(ForeignKey("users.id"))


class Holiday(TimestampMixin, Base):
    """A non-working day; `branch_id` NULL means school-wide."""

    __tablename__ = "holidays"
    __table_args__ = (
        # Two partial unique indexes so the NULL (school-wide) case is also unique.
        Index(
            "uq_holidays_branch_date",
            "school_id",
            "branch_id",
            "date",
            unique=True,
            sqlite_where=text("branch_id IS NOT NULL"),
            postgresql_where=text("branch_id IS NOT NULL"),
        ),
        Index(
            "uq_holidays_school_date",
            "school_id",
            "date",
            unique=True,
            sqlite_where=text("branch_id IS NULL"),
            postgresql_where=text("branch_id IS NULL"),
        ),
        ForeignKeyConstraint(["branch_id", "school_id"], ["branches.id", "branches.school_id"]),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    school_id: Mapped[int] = mapped_column(index=True)
    branch_id: Mapped[int | None] = mapped_column()
    date: Mapped[date] = mapped_column(Date, index=True)
    name: Mapped[str] = mapped_column(String(100))
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
