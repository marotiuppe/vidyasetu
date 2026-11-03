import enum
from datetime import date

from sqlalchemy import (
    Boolean,
    Date,
    Enum,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class Gender(enum.StrEnum):
    MALE = "male"
    FEMALE = "female"
    OTHER = "other"


class StudentStatus(enum.StrEnum):
    ACTIVE = "active"
    LEFT = "left"
    TRANSFERRED = "transferred"
    PASSED_OUT = "passed_out"


class GuardianRelation(enum.StrEnum):
    FATHER = "father"
    MOTHER = "mother"
    GUARDIAN = "guardian"
    OTHER = "other"


def _enum(e: type[enum.StrEnum], length: int = 20) -> Enum:
    return Enum(e, native_enum=False, length=length, values_callable=lambda x: [m.value for m in x])


class Student(TimestampMixin, Base):
    """A student; belongs to exactly one branch of one school at a time."""

    __tablename__ = "students"
    __table_args__ = (
        UniqueConstraint("school_id", "admission_no"),
        UniqueConstraint("id", "school_id"),
        UniqueConstraint("id", "branch_id"),
        ForeignKeyConstraint(["branch_id", "school_id"], ["branches.id", "branches.school_id"]),
        # A PEN is unique within a school (only when one is recorded).
        Index(
            "uq_students_school_pen",
            "school_id",
            "pen",
            unique=True,
            sqlite_where=text("pen IS NOT NULL"),
            postgresql_where=text("pen IS NOT NULL"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    school_id: Mapped[int] = mapped_column(index=True)
    branch_id: Mapped[int] = mapped_column(index=True)
    admission_no: Mapped[str] = mapped_column(String(50))
    first_name: Mapped[str] = mapped_column(String(100))
    last_name: Mapped[str] = mapped_column(String(100))
    gender: Mapped[Gender] = mapped_column(_enum(Gender))
    date_of_birth: Mapped[date] = mapped_column(Date)
    admission_date: Mapped[date] = mapped_column(Date)
    status: Mapped[StudentStatus] = mapped_column(
        _enum(StudentStatus), default=StudentStatus.ACTIVE
    )
    address: Mapped[str | None] = mapped_column(Text)
    previous_school: Mapped[str | None] = mapped_column(String(200))
    # The student's own login (role student).
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), unique=True)
    # Government identifiers (only when the school enabled students.gov_ids_enabled). The
    # Aadhaar number is never stored; `aadhaar_details_match` only records that staff checked it.
    pen: Mapped[str | None] = mapped_column(String(11))
    apaar_id: Mapped[str | None] = mapped_column(String(12))
    # None = not asked, True = given, False = refused (then apaar_id is cleared).
    apaar_consent: Mapped[bool | None] = mapped_column(Boolean)
    aadhaar_details_match: Mapped[bool | None] = mapped_column(Boolean)


class Guardian(TimestampMixin, Base):
    """A parent/guardian of a student. The same parent login may be linked to many guardians."""

    __tablename__ = "guardians"
    __table_args__ = (
        ForeignKeyConstraint(["student_id", "school_id"], ["students.id", "students.school_id"]),
        # At most one primary guardian per student (the service keeps it at exactly one).
        Index(
            "uq_guardians_one_primary",
            "student_id",
            unique=True,
            sqlite_where=text("is_primary"),
            postgresql_where=text("is_primary"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    school_id: Mapped[int] = mapped_column(index=True)
    student_id: Mapped[int] = mapped_column(index=True)
    full_name: Mapped[str] = mapped_column(String(200))
    relation: Mapped[GuardianRelation] = mapped_column(_enum(GuardianRelation))
    phone: Mapped[str] = mapped_column(String(20))
    email: Mapped[str | None] = mapped_column(String(254))
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), index=True)


class Enrollment(TimestampMixin, Base):
    """A student's placement (class/section/roll number) in one academic year."""

    __tablename__ = "enrollments"
    __table_args__ = (
        UniqueConstraint("student_id", "academic_year_id"),
        UniqueConstraint("section_id", "academic_year_id", "roll_no"),
        ForeignKeyConstraint(["student_id", "school_id"], ["students.id", "students.school_id"]),
        ForeignKeyConstraint(["class_id", "branch_id"], ["classes.id", "classes.branch_id"]),
        ForeignKeyConstraint(["branch_id", "school_id"], ["branches.id", "branches.school_id"]),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    school_id: Mapped[int] = mapped_column(index=True)
    branch_id: Mapped[int] = mapped_column(index=True)
    student_id: Mapped[int] = mapped_column()
    academic_year_id: Mapped[int] = mapped_column(ForeignKey("academic_years.id"), index=True)
    class_id: Mapped[int] = mapped_column(index=True)
    section_id: Mapped[int | None] = mapped_column(ForeignKey("sections.id"), index=True)
    roll_no: Mapped[int | None] = mapped_column(SmallInteger)
