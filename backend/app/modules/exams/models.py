"""Exams and report cards: terms, subjects, class subjects, exams, marks, grading scales,
report aspects (co-scholastic and HPC sections), aspect grades and term remarks.

Every table carries school_id and branch_id (grading scales are school-wide). Links to students
and branch tables use the composite keys used elsewhere, so a row cannot point across branches.
"""

import enum
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Enum,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class SubjectKind(enum.StrEnum):
    SCHOLASTIC = "scholastic"
    CO_SCHOLASTIC = "co_scholastic"


class AspectSection(enum.StrEnum):
    CO_CURRICULAR = "co_curricular"
    BEHAVIOURAL = "behavioural"
    SELF_AWARENESS = "self_awareness"
    HEALTH = "health"


class AspectGradeValue(enum.StrEnum):
    A = "A"
    B = "B"
    C = "C"
    D = "D"
    E = "E"


def _enum(e: type[enum.StrEnum], length: int = 20) -> Enum:
    return Enum(e, native_enum=False, length=length, values_callable=lambda x: [m.value for m in x])


class ExamTerm(TimestampMixin, Base):
    """A term of an academic year (e.g. first term, second term) within one branch."""

    __tablename__ = "exam_terms"
    __table_args__ = (
        UniqueConstraint("branch_id", "academic_year_id", "name"),
        UniqueConstraint("id", "branch_id"),
        ForeignKeyConstraint(["branch_id", "school_id"], ["branches.id", "branches.school_id"]),
        CheckConstraint("weight_percent >= 0 AND weight_percent <= 100", "ck_exam_terms_weight"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    school_id: Mapped[int] = mapped_column(index=True)
    branch_id: Mapped[int] = mapped_column(index=True)
    academic_year_id: Mapped[int] = mapped_column(ForeignKey("academic_years.id"), index=True)
    name: Mapped[str] = mapped_column(String(50))
    sequence: Mapped[int] = mapped_column(Integer)
    weight_percent: Mapped[int] = mapped_column(Integer)


class Subject(TimestampMixin, Base):
    """A subject taught in one branch (scholastic or co-scholastic)."""

    __tablename__ = "subjects"
    __table_args__ = (
        UniqueConstraint("branch_id", "name"),
        UniqueConstraint("id", "branch_id"),
        ForeignKeyConstraint(["branch_id", "school_id"], ["branches.id", "branches.school_id"]),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    school_id: Mapped[int] = mapped_column(index=True)
    branch_id: Mapped[int] = mapped_column(index=True)
    name: Mapped[str] = mapped_column(String(80))
    code: Mapped[str | None] = mapped_column(String(20))
    kind: Mapped[SubjectKind] = mapped_column(_enum(SubjectKind), default=SubjectKind.SCHOLASTIC)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class ClassSubject(TimestampMixin, Base):
    """Which subjects a class studies."""

    __tablename__ = "class_subjects"
    __table_args__ = (
        UniqueConstraint("class_id", "subject_id"),
        ForeignKeyConstraint(["class_id", "branch_id"], ["classes.id", "classes.branch_id"]),
        ForeignKeyConstraint(["subject_id", "branch_id"], ["subjects.id", "subjects.branch_id"]),
        ForeignKeyConstraint(["branch_id", "school_id"], ["branches.id", "branches.school_id"]),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    school_id: Mapped[int] = mapped_column(index=True)
    branch_id: Mapped[int] = mapped_column(index=True)
    class_id: Mapped[int] = mapped_column(index=True)
    subject_id: Mapped[int] = mapped_column(index=True)


class Exam(TimestampMixin, Base):
    """One assessment inside a term (e.g. Unit Test 1). Families never see unpublished exams."""

    __tablename__ = "exams"
    __table_args__ = (
        UniqueConstraint("term_id", "name"),
        UniqueConstraint("id", "branch_id"),
        ForeignKeyConstraint(["term_id", "branch_id"], ["exam_terms.id", "exam_terms.branch_id"]),
        ForeignKeyConstraint(["branch_id", "school_id"], ["branches.id", "branches.school_id"]),
        CheckConstraint("max_marks >= 1 AND max_marks <= 1000", "ck_exams_max_marks"),
        CheckConstraint("weight_percent >= 0 AND weight_percent <= 100", "ck_exams_weight"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    school_id: Mapped[int] = mapped_column(index=True)
    branch_id: Mapped[int] = mapped_column(index=True)
    term_id: Mapped[int] = mapped_column(index=True)
    name: Mapped[str] = mapped_column(String(80))
    max_marks: Mapped[int] = mapped_column(Integer)
    weight_percent: Mapped[int] = mapped_column(Integer)
    published: Mapped[bool] = mapped_column(Boolean, default=False)
    locked: Mapped[bool] = mapped_column(Boolean, default=False)


class ExamMark(TimestampMixin, Base):
    """One student's marks in one subject of one exam. `marks` NULL with absent False means
    the mark is not entered yet."""

    __tablename__ = "exam_marks"
    __table_args__ = (
        UniqueConstraint("exam_id", "student_id", "subject_id"),
        ForeignKeyConstraint(["exam_id", "branch_id"], ["exams.id", "exams.branch_id"]),
        ForeignKeyConstraint(["student_id", "school_id"], ["students.id", "students.school_id"]),
        ForeignKeyConstraint(["subject_id", "branch_id"], ["subjects.id", "subjects.branch_id"]),
        ForeignKeyConstraint(["branch_id", "school_id"], ["branches.id", "branches.school_id"]),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    school_id: Mapped[int] = mapped_column(index=True)
    branch_id: Mapped[int] = mapped_column(index=True)
    exam_id: Mapped[int] = mapped_column(index=True)
    student_id: Mapped[int] = mapped_column(index=True)
    subject_id: Mapped[int] = mapped_column(index=True)
    marks: Mapped[Decimal | None] = mapped_column(Numeric(6, 2, asdecimal=True))
    absent: Mapped[bool] = mapped_column(Boolean, default=False)
    entered_by: Mapped[int] = mapped_column(ForeignKey("users.id"))


class GradeScale(TimestampMixin, Base):
    """A grading scale of one school. Exactly one scale per school is the default."""

    __tablename__ = "grade_scales"
    __table_args__ = (
        UniqueConstraint("school_id", "name"),
        # At most one default scale per school.
        Index(
            "uq_grade_scales_one_default",
            "school_id",
            unique=True,
            sqlite_where=text("is_default"),
            postgresql_where=text("is_default"),
        ),
        CheckConstraint("pass_percent >= 0 AND pass_percent <= 100", "ck_grade_scales_pass"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    school_id: Mapped[int] = mapped_column(ForeignKey("schools.id"), index=True)
    name: Mapped[str] = mapped_column(String(50))
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    pass_percent: Mapped[int] = mapped_column(Integer, default=33)


class GradeBand(Base):
    """One band of a scale: percentages from `min_percent` up to the next band's minimum."""

    __tablename__ = "grade_bands"
    __table_args__ = (
        UniqueConstraint("scale_id", "min_percent"),
        CheckConstraint("min_percent >= 0 AND min_percent <= 100", "ck_grade_bands_min"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    scale_id: Mapped[int] = mapped_column(
        ForeignKey("grade_scales.id", ondelete="CASCADE"), index=True
    )
    min_percent: Mapped[int] = mapped_column(Integer)
    grade: Mapped[str] = mapped_column(String(10))
    grade_point: Mapped[Decimal | None] = mapped_column(Numeric(4, 1, asdecimal=True))
    remark: Mapped[str | None] = mapped_column(String(60))


class ReportAspect(TimestampMixin, Base):
    """A co-curricular, behavioural, self-awareness or health aspect graded per term (HPC style)."""

    __tablename__ = "report_aspects"
    __table_args__ = (
        UniqueConstraint("branch_id", "section", "name"),
        UniqueConstraint("id", "branch_id"),
        ForeignKeyConstraint(["branch_id", "school_id"], ["branches.id", "branches.school_id"]),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    school_id: Mapped[int] = mapped_column(index=True)
    branch_id: Mapped[int] = mapped_column(index=True)
    section: Mapped[AspectSection] = mapped_column(_enum(AspectSection))
    name: Mapped[str] = mapped_column(String(80))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    sequence: Mapped[int] = mapped_column(Integer, default=0)


class AspectGrade(TimestampMixin, Base):
    """A student's grade (A to E) for one aspect in one term, with an optional remark."""

    __tablename__ = "aspect_grades"
    __table_args__ = (
        UniqueConstraint("term_id", "student_id", "aspect_id"),
        ForeignKeyConstraint(["term_id", "branch_id"], ["exam_terms.id", "exam_terms.branch_id"]),
        ForeignKeyConstraint(
            ["aspect_id", "branch_id"], ["report_aspects.id", "report_aspects.branch_id"]
        ),
        ForeignKeyConstraint(["student_id", "school_id"], ["students.id", "students.school_id"]),
        ForeignKeyConstraint(["branch_id", "school_id"], ["branches.id", "branches.school_id"]),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    school_id: Mapped[int] = mapped_column(index=True)
    branch_id: Mapped[int] = mapped_column(index=True)
    term_id: Mapped[int] = mapped_column(index=True)
    student_id: Mapped[int] = mapped_column(index=True)
    aspect_id: Mapped[int] = mapped_column(index=True)
    grade: Mapped[AspectGradeValue] = mapped_column(_enum(AspectGradeValue, length=1))
    remark: Mapped[str | None] = mapped_column(String(200))
    entered_by: Mapped[int] = mapped_column(ForeignKey("users.id"))


class TermRemark(TimestampMixin, Base):
    """The class teacher's remark on a student for one term."""

    __tablename__ = "term_remarks"
    __table_args__ = (
        UniqueConstraint("term_id", "student_id"),
        ForeignKeyConstraint(["term_id", "branch_id"], ["exam_terms.id", "exam_terms.branch_id"]),
        ForeignKeyConstraint(["student_id", "school_id"], ["students.id", "students.school_id"]),
        ForeignKeyConstraint(["branch_id", "school_id"], ["branches.id", "branches.school_id"]),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    school_id: Mapped[int] = mapped_column(index=True)
    branch_id: Mapped[int] = mapped_column(index=True)
    term_id: Mapped[int] = mapped_column(index=True)
    student_id: Mapped[int] = mapped_column(index=True)
    remark: Mapped[str | None] = mapped_column(Text)
    entered_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
