"""Response schemas for report cards, progress charts and class summaries.

Nothing here is stored: every figure is computed from marks when the response is built.
"""

from datetime import date

from pydantic import BaseModel

from app.modules.exams.models import AspectSection, SubjectKind
from app.modules.exams.schemas import BandOut, ExamRefOut, Score, SectionRefOut


class ExamEntryOut(BaseModel):
    exam_id: int
    name: str
    max_marks: int
    weight_used: Score
    published: bool
    entered: bool
    absent: bool
    marks: Score
    percent: Score


class SubjectTermOut(BaseModel):
    subject_id: int
    name: str
    code: str | None
    kind: SubjectKind
    percent: Score
    grade: str | None
    grade_point: Score
    result: str | None
    complete: bool
    exams: list[ExamEntryOut]


class AspectReportOut(BaseModel):
    aspect_id: int
    section: AspectSection
    name: str
    grade: str | None
    remark: str | None


class TermReportOut(BaseModel):
    term_id: int
    name: str
    sequence: int
    weight_percent: int
    exam_weighting: str
    subjects: list[SubjectTermOut]
    total: Score
    grade: str | None
    grade_point: Score
    band_remark: str | None
    result: str | None
    complete: bool
    rank: int | None
    aspects: list[AspectReportOut]
    teacher_remark: str | None


class AnnualSubjectOut(BaseModel):
    subject_id: int
    name: str
    kind: SubjectKind
    percent: Score
    grade: str | None
    result: str | None


class AnnualOut(BaseModel):
    term_weighting: str
    total: Score
    grade: str | None
    grade_point: Score
    result: str | None
    rank: int | None
    subjects: list[AnnualSubjectOut]


class AttendanceOut(BaseModel):
    present: int
    marked_days: int
    percentage: Score


class ReportStudentOut(BaseModel):
    id: int
    name: str
    admission_no: str
    date_of_birth: date
    guardian_name: str | None


class ReportOut(BaseModel):
    student: ReportStudentOut
    school_id: int
    school_name: str
    branch_id: int
    branch_name: str
    academic_year_id: int
    academic_year_name: str
    class_name: str | None
    section_name: str | None
    roll_no: int | None
    report_format: str
    aspect_sections: list[AspectSection]
    pass_percent: int
    grading: list[BandOut]
    include_unpublished: bool
    show_rank: bool
    principal_name: str | None
    footer: str | None
    attendance: AttendanceOut | None
    terms: list[TermReportOut]
    annual: AnnualOut | None


class ProgressPointOut(BaseModel):
    term_id: int
    percent: Score


class ProgressTermOut(BaseModel):
    term_id: int
    name: str
    sequence: int


class ProgressSubjectOut(BaseModel):
    subject_id: int
    name: str
    kind: SubjectKind
    points: list[ProgressPointOut]


class ProgressOut(BaseModel):
    student_id: int
    academic_year_id: int
    terms: list[ProgressTermOut]
    subjects: list[ProgressSubjectOut]
    totals: list[ProgressPointOut]


class ClassSubjectStatOut(BaseModel):
    subject_id: int
    name: str
    kind: SubjectKind
    entered: int
    absent: int
    average_percent: Score
    highest_percent: Score
    lowest_percent: Score
    fail_count: int


class ClassOverallOut(BaseModel):
    average_percent: Score
    highest_percent: Score
    lowest_percent: Score
    fail_count: int


class ClassSummaryOut(BaseModel):
    exam: ExamRefOut
    section: SectionRefOut
    pass_percent: int
    students_count: int
    entered_count: int
    subjects: list[ClassSubjectStatOut]
    overall: ClassOverallOut
