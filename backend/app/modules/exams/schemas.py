"""Request and response schemas for exam configuration, marks entry, aspect grades and remarks.

Marks and percentages are Decimal in Python and are sent as JSON numbers with at most two
decimals. Report schemas live in report_schemas.py.
"""

from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, PlainSerializer, StringConstraints

from app.modules.exams.models import AspectGradeValue, AspectSection, SubjectKind


def _as_number(value: Decimal | None) -> float | None:
    return None if value is None else float(value)


# Decimal values leave the API as JSON numbers (exact to two decimals); inside the server they
# stay Decimal.
Score = Annotated[Decimal | None, PlainSerializer(_as_number, when_used="json")]

Name50 = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=50)]
Name80 = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]
Name200 = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
# Optional text for PATCH bodies: the constraint sits on the str inside the union, so an explicit
# null is accepted as "no change" and never reaches the length check.
OptName50 = (
    Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=50)] | None
)
OptName80 = (
    Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)] | None
)
OptCode20 = Annotated[str, StringConstraints(strip_whitespace=True, max_length=20)] | None


class _In(BaseModel):
    model_config = ConfigDict(extra="forbid")


# ---- terms ----


class TermIn(_In):
    academic_year_id: int = Field(ge=1)
    name: Name50
    sequence: int = Field(ge=1, le=20)
    weight_percent: int = Field(ge=0, le=100)


class TermPatch(_In):
    name: OptName50 = None
    sequence: int | None = Field(default=None, ge=1, le=20)
    weight_percent: int | None = Field(default=None, ge=0, le=100)


class TermOut(BaseModel):
    id: int
    branch_id: int
    academic_year_id: int
    name: str
    sequence: int
    weight_percent: int


# ---- subjects ----


class SubjectIn(_In):
    name: Name80
    code: OptCode20 = None
    kind: SubjectKind = SubjectKind.SCHOLASTIC
    active: bool = True


class SubjectPatch(_In):
    name: OptName80 = None
    code: OptCode20 = None
    kind: SubjectKind | None = None
    active: bool | None = None


class SubjectOut(BaseModel):
    id: int
    branch_id: int
    name: str
    code: str | None
    kind: SubjectKind
    active: bool


class ClassSubjectsPut(_In):
    class_id: int = Field(ge=1)
    subject_ids: list[int] = Field(max_length=60)


class ClassSubjectsOut(BaseModel):
    class_id: int
    class_name: str
    subjects: list[SubjectOut]


# ---- exams ----


class ExamIn(_In):
    term_id: int = Field(ge=1)
    name: Name80
    max_marks: int = Field(ge=1, le=1000)
    weight_percent: int = Field(ge=0, le=100)
    published: bool = False
    locked: bool = False


class ExamPatch(_In):
    name: OptName80 = None
    max_marks: int | None = Field(default=None, ge=1, le=1000)
    weight_percent: int | None = Field(default=None, ge=0, le=100)
    published: bool | None = None
    locked: bool | None = None


class ExamOut(BaseModel):
    id: int
    branch_id: int
    term_id: int
    term_name: str
    name: str
    max_marks: int
    weight_percent: int
    published: bool
    locked: bool


# ---- grading ----


class BandIn(_In):
    min_percent: int = Field(ge=0, le=100)
    grade: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=10)]
    grade_point: Decimal | None = Field(default=None, ge=0, le=10)
    remark: Annotated[str, StringConstraints(strip_whitespace=True, max_length=60)] | None = None


class BandOut(BaseModel):
    min_percent: int
    grade: str
    grade_point: Score
    remark: str | None


class GradingPut(_In):
    name: OptName50 = None
    pass_percent: int = Field(ge=0, le=100)
    bands: list[BandIn] = Field(min_length=1, max_length=20)


class GradingOut(BaseModel):
    id: int
    name: str
    is_default: bool
    pass_percent: int
    bands: list[BandOut]


# ---- report aspects ----


class AspectIn(_In):
    section: AspectSection
    name: Name80
    active: bool = True
    sequence: int = Field(default=0, ge=0, le=999)


class AspectPatch(_In):
    name: OptName80 = None
    active: bool | None = None
    sequence: int | None = Field(default=None, ge=0, le=999)


class AspectOut(BaseModel):
    id: int
    branch_id: int
    section: AspectSection
    name: str
    active: bool
    sequence: int


# ---- marks entry ----


class MarkRow(_In):
    student_id: int = Field(ge=1)
    marks: Decimal | None = None
    absent: bool = False


class MarksPut(_In):
    exam_id: int = Field(ge=1)
    subject_id: int = Field(ge=1)
    section_id: int = Field(ge=1)
    rows: list[MarkRow] = Field(min_length=1, max_length=200)


class MarkStudentOut(BaseModel):
    student_id: int
    name: str
    roll_no: int | None
    marks: Score
    absent: bool


class ExamRefOut(BaseModel):
    id: int
    name: str
    max_marks: int
    published: bool
    locked: bool
    term_id: int
    term_name: str


class SubjectRefOut(BaseModel):
    id: int
    name: str
    kind: SubjectKind


class SectionRefOut(BaseModel):
    id: int
    name: str
    class_id: int
    class_name: str


class MarksOut(BaseModel):
    exam: ExamRefOut
    subject: SubjectRefOut
    section: SectionRefOut
    students: list[MarkStudentOut]


# ---- aspect grades and term remarks ----


class AspectRow(_In):
    student_id: int = Field(ge=1)
    aspect_id: int = Field(ge=1)
    grade: AspectGradeValue | None = None
    remark: Annotated[str, StringConstraints(strip_whitespace=True, max_length=200)] | None = None


class AspectGradesPut(_In):
    term_id: int = Field(ge=1)
    section_id: int = Field(ge=1)
    rows: list[AspectRow] = Field(min_length=1, max_length=200)


class AspectCellOut(BaseModel):
    aspect_id: int
    grade: AspectGradeValue | None
    remark: str | None


class AspectStudentOut(BaseModel):
    student_id: int
    name: str
    roll_no: int | None
    grades: list[AspectCellOut]


class AspectGradesOut(BaseModel):
    term_id: int
    term_name: str
    section: SectionRefOut
    aspects: list[AspectOut]
    students: list[AspectStudentOut]


class TermRemarkRow(_In):
    student_id: int = Field(ge=1)
    remark: Annotated[str, StringConstraints(strip_whitespace=True, max_length=500)] | None = None


class TermRemarksPut(_In):
    rows: list[TermRemarkRow] = Field(min_length=1, max_length=200)


class TermRemarkStudentOut(BaseModel):
    student_id: int
    name: str
    roll_no: int | None
    remark: str | None


class TermRemarksOut(BaseModel):
    term_id: int
    term_name: str
    section: SectionRefOut
    students: list[TermRemarkStudentOut]
