"""Report cards, progress and class summaries. Nothing is stored here: every figure is worked out
from the marks at the time of the request, using the rules in calc.py.

Visibility: families (parents, students) see only their own students, only when the school allows
results (portal.parent_sees_results), and only published exams. Staff see unpublished exams when
they ask for them with include_unpublished. Rank is computed among the same visible figures.
"""

from dataclasses import dataclass
from decimal import Decimal
from typing import Literal

from fastapi import status
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ApiError
from app.core.tenant import scope_students
from app.modules.academics.models import AcademicYear, SchoolClass, Section
from app.modules.attendance.models import AttendanceRecord, AttendanceStatus
from app.modules.audit import service as audit
from app.modules.branches.models import Branch
from app.modules.exams import common
from app.modules.exams.calc import (
    AnnualCalc,
    BandRef,
    ExamRef,
    MarkRef,
    ScaleRef,
    SubjectRef,
    TermCalc,
    TermRef,
    annual_calc,
    band_for,
    competition_rank,
    exam_percent,
    q2,
    term_calc,
)
from app.modules.exams.common import FAMILY_ROLES, RESULT_STAFF_ROLES, student_name
from app.modules.exams.config_service import configured_sections, scale_for
from app.modules.exams.models import (
    AspectGrade,
    AspectSection,
    ClassSubject,
    Exam,
    ExamMark,
    ExamTerm,
    ReportAspect,
    Subject,
    SubjectKind,
    TermRemark,
)
from app.modules.exams.pdf import build_report_pdf
from app.modules.exams.report_schemas import (
    AnnualOut,
    AnnualSubjectOut,
    AspectReportOut,
    AttendanceOut,
    ClassOverallOut,
    ClassSubjectStatOut,
    ClassSummaryOut,
    ExamEntryOut,
    ProgressOut,
    ProgressPointOut,
    ProgressSubjectOut,
    ProgressTermOut,
    ReportOut,
    ReportStudentOut,
    SubjectTermOut,
    TermReportOut,
)
from app.modules.exams.schemas import BandOut, ExamRefOut, SectionRefOut
from app.modules.schools.models import School, SchoolLogo
from app.modules.settings import service as settings_service
from app.modules.students.models import Enrollment, Guardian, Student, StudentStatus
from app.modules.users.models import User

_PORTAL_KEY = "portal.parent_sees_results"
_ATTENDANCE_KEY = "portal.parent_sees_attendance"


@dataclass
class _Context:
    """Everything a report needs for one class and year, loaded in a fixed number of queries."""

    terms: list[TermRef]
    term_exams: dict[int, list[ExamRef]]
    subjects: list[SubjectRef]
    marks: dict[int, dict[tuple[int, int], MarkRef]]  # student_id -> (exam_id, subject_id)
    scale: ScaleRef
    show_unpublished: bool


def _forbidden() -> ApiError:
    return ApiError(status.HTTP_403_FORBIDDEN, "Not allowed", "forbidden")


def _is_family(actor: User) -> bool:
    """True for a parent or student. Raises for roles that never see results."""
    if actor.role in FAMILY_ROLES:
        return True
    if actor.role not in RESULT_STAFF_ROLES:
        raise _forbidden()
    return False


async def _student_for(db: AsyncSession, actor: User, student_id: int) -> Student:
    student: Student | None = await db.scalar(
        scope_students(select(Student), actor).where(Student.id == student_id)
    )
    if student is None:
        raise common.not_found("Student")
    return student


async def _year_for(db: AsyncSession, student: Student, year_id: int) -> AcademicYear:
    year: AcademicYear | None = await db.scalar(
        select(AcademicYear).where(
            AcademicYear.id == year_id, AcademicYear.school_id == student.school_id
        )
    )
    if year is None:
        raise common.not_found("Academic year")
    return year


async def _load_context(
    db: AsyncSession,
    *,
    school_id: int,
    branch_id: int,
    year_id: int,
    class_id: int,
    mate_ids: list[int],
    show_unpublished: bool,
) -> _Context:
    term_rows = list(
        await db.scalars(
            select(ExamTerm)
            .where(ExamTerm.branch_id == branch_id, ExamTerm.academic_year_id == year_id)
            .order_by(ExamTerm.sequence, ExamTerm.id)
        )
    )
    exam_rows: list[Exam] = []
    if term_rows:
        exam_rows = list(
            await db.scalars(
                select(Exam).where(Exam.term_id.in_([t.id for t in term_rows])).order_by(Exam.id)
            )
        )
    subjects = [
        SubjectRef(id=s.id, name=s.name, code=s.code, scholastic=s.kind == SubjectKind.SCHOLASTIC)
        for s in await db.scalars(
            select(Subject)
            .join(ClassSubject, ClassSubject.subject_id == Subject.id)
            .where(ClassSubject.class_id == class_id)
        )
    ]
    subjects.sort(key=lambda s: (not s.scholastic, s.name))
    marks: dict[int, dict[tuple[int, int], MarkRef]] = {sid: {} for sid in mate_ids}
    if exam_rows and subjects and mate_ids:
        for mark in await db.scalars(
            select(ExamMark).where(
                ExamMark.exam_id.in_([e.id for e in exam_rows]),
                ExamMark.subject_id.in_([s.id for s in subjects]),
                ExamMark.student_id.in_(mate_ids),
            )
        ):
            marks.setdefault(mark.student_id, {})[(mark.exam_id, mark.subject_id)] = MarkRef(
                marks=mark.marks, absent=mark.absent
            )
    by_term: dict[int, list[ExamRef]] = {t.id: [] for t in term_rows}
    for e in exam_rows:
        by_term.setdefault(e.term_id, []).append(
            ExamRef(e.id, e.term_id, e.name, e.max_marks, e.weight_percent, e.published)
        )
    return _Context(
        terms=[TermRef(t.id, t.name, t.sequence, t.weight_percent) for t in term_rows],
        term_exams=by_term,
        subjects=subjects,
        marks=marks,
        scale=await scale_for(db, school_id),
        show_unpublished=show_unpublished,
    )


def _calc(ctx: _Context, student_id: int) -> tuple[list[TermCalc], AnnualCalc]:
    """Term figures for the terms that have at least one visible exam, and the annual figures."""
    included: list[TermCalc] = []
    student_marks = ctx.marks.get(student_id, {})
    for term in ctx.terms:
        all_exams = ctx.term_exams.get(term.id, [])
        visible = [e for e in all_exams if ctx.show_unpublished or e.published]
        if visible:
            included.append(
                term_calc(term, all_exams, visible, ctx.subjects, student_marks, ctx.scale)
            )
    annual = annual_calc(included, [t.weight for t in ctx.terms], ctx.subjects, ctx.scale)
    return included, annual


def _kind(subject: SubjectRef) -> SubjectKind:
    return SubjectKind.SCHOLASTIC if subject.scholastic else SubjectKind.CO_SCHOLASTIC


def _band_out(scale: ScaleRef) -> list[BandOut]:
    return [
        BandOut(
            min_percent=b.min_percent, grade=b.grade, grade_point=b.grade_point, remark=b.remark
        )
        for b in scale.bands
    ]


def _grade(scale: ScaleRef, percent: Decimal | None) -> BandRef | None:
    return band_for(scale, percent)


def _grade_code(scale: ScaleRef, percent: Decimal | None) -> str | None:
    band = band_for(scale, percent)
    return band.grade if band is not None else None


async def _attendance(db: AsyncSession, student: Student, year: AcademicYear) -> AttendanceOut:
    present_flag = case((AttendanceRecord.status == AttendanceStatus.PRESENT, 1), else_=0)
    row = (
        await db.execute(
            select(func.count(AttendanceRecord.id), func.sum(present_flag)).where(
                AttendanceRecord.student_id == student.id,
                AttendanceRecord.date >= year.start_date,
                AttendanceRecord.date <= year.end_date,
            )
        )
    ).one()
    marked = int(row[0] or 0)
    present = int(row[1] or 0)
    pct = q2(Decimal(present) * 100 / Decimal(marked)) if marked else None
    return AttendanceOut(present=present, marked_days=marked, percentage=pct)


async def _aspects(
    db: AsyncSession, branch_id: int, sections: list[AspectSection]
) -> list[ReportAspect]:
    if not sections:
        return []
    rows = await db.scalars(
        select(ReportAspect)
        .where(
            ReportAspect.branch_id == branch_id,
            ReportAspect.active.is_(True),
            ReportAspect.section.in_(sections),
        )
        .order_by(ReportAspect.section, ReportAspect.sequence, ReportAspect.name)
    )
    return list(rows)


async def _enrolment(
    db: AsyncSession, student: Student, year: AcademicYear
) -> tuple[Enrollment, str, str | None]:
    row = (
        await db.execute(
            select(Enrollment, SchoolClass.name, Section.name)
            .join(SchoolClass, SchoolClass.id == Enrollment.class_id)
            .outerjoin(Section, Section.id == Enrollment.section_id)
            .where(Enrollment.student_id == student.id, Enrollment.academic_year_id == year.id)
        )
    ).first()
    if row is None:
        raise common.not_found("Enrolment for this year")
    return row[0], row[1], row[2]


async def _section_mates(
    db: AsyncSession, enrol: Enrollment, year_id: int, student_id: int
) -> list[int]:
    """Active students of the same section (for rank), always including the student."""
    if enrol.section_id is None:
        return [student_id]
    ids = await db.scalars(
        select(Enrollment.student_id)
        .join(Student, Student.id == Enrollment.student_id)
        .where(
            Enrollment.section_id == enrol.section_id,
            Enrollment.academic_year_id == year_id,
            Student.status == StudentStatus.ACTIVE,
        )
    )
    return sorted(set(ids) | {student_id})


def _term_out(
    tc: TermCalc,
    ctx: _Context,
    aspects: list[ReportAspect],
    grades: dict[tuple[int, int], AspectGrade],
    remarks: dict[int, str | None],
    rank: int | None,
) -> TermReportOut:
    subjects_out: list[SubjectTermOut] = []
    for st in tc.subjects:
        band = _grade(ctx.scale, st.percent)
        exams_out = [
            ExamEntryOut(
                exam_id=e.exam.id,
                name=e.exam.name,
                max_marks=e.exam.max_marks,
                weight_used=e.weight,
                published=e.exam.published,
                entered=e.percent is not None,
                absent=bool(e.mark and e.mark.absent),
                marks=e.mark.marks if e.mark else None,
                percent=e.percent,
            )
            for e in st.entries
        ]
        subjects_out.append(
            SubjectTermOut(
                subject_id=st.subject.id,
                name=st.subject.name,
                code=st.subject.code,
                kind=_kind(st.subject),
                percent=st.percent,
                grade=band.grade if band else None,
                grade_point=band.grade_point if band else None,
                result=st.result(ctx.scale),
                complete=st.complete,
                exams=exams_out,
            )
        )
    total_band = _grade(ctx.scale, tc.total)
    aspect_out: list[AspectReportOut] = []
    for a in aspects:
        cell = grades.get((tc.term.id, a.id))
        aspect_out.append(
            AspectReportOut(
                aspect_id=a.id,
                section=a.section,
                name=a.name,
                grade=cell.grade.value if cell else None,
                remark=cell.remark if cell else None,
            )
        )
    return TermReportOut(
        term_id=tc.term.id,
        name=tc.term.name,
        sequence=tc.term.sequence,
        weight_percent=tc.term.weight,
        exam_weighting=tc.exam_weighting,
        subjects=subjects_out,
        total=tc.total,
        grade=total_band.grade if total_band else None,
        grade_point=total_band.grade_point if total_band else None,
        band_remark=total_band.remark if total_band else None,
        result=tc.result,
        complete=tc.complete,
        rank=rank,
        aspects=aspect_out,
        teacher_remark=remarks.get(tc.term.id),
    )


def _annual_out(annual: AnnualCalc, ctx: _Context, rank: int | None) -> AnnualOut:
    total_band = _grade(ctx.scale, annual.total)
    return AnnualOut(
        term_weighting=annual.term_weighting,
        total=annual.total,
        grade=total_band.grade if total_band else None,
        grade_point=total_band.grade_point if total_band else None,
        result=annual.result,
        rank=rank,
        subjects=[
            AnnualSubjectOut(
                subject_id=s.subject.id,
                name=s.subject.name,
                kind=_kind(s.subject),
                percent=s.percent,
                grade=_grade_code(ctx.scale, s.percent),
                result=s.result(ctx.scale),
            )
            for s in annual.subjects
        ],
    )


async def build_report(
    db: AsyncSession,
    actor: User,
    student_id: int,
    academic_year_id: int,
    *,
    include_unpublished: bool,
    format_override: str | None,
) -> ReportOut:
    family = _is_family(actor)
    if family:
        await settings_service.require_family_portal(db, actor, _PORTAL_KEY)
    student = await _student_for(db, actor, student_id)
    year = await _year_for(db, student, academic_year_id)
    enrol, class_name, section_name = await _enrolment(db, student, year)
    school_id = student.school_id
    show_unpublished = include_unpublished and not family
    report_format = format_override or (
        await settings_service.get_str(db, "exams.report_format", school_id=school_id) or "cbse"
    )
    sections = configured_sections(
        await settings_service.get_str(db, "exams.report_sections", school_id=school_id)
    )
    show_rank = await settings_service.get_bool(db, "exams.show_rank", school_id=school_id)
    mates = await _section_mates(db, enrol, year.id, student.id) if show_rank else [student.id]
    ctx = await _load_context(
        db,
        school_id=school_id,
        branch_id=student.branch_id,
        year_id=year.id,
        class_id=enrol.class_id,
        mate_ids=mates,
        show_unpublished=show_unpublished,
    )
    included, annual = _calc(ctx, student.id)

    term_ranks: dict[int, int | None] = {}
    annual_rank: int | None = None
    if show_rank:
        per_mate = {mid: _calc(ctx, mid) for mid in mates}
        for tc in included:
            totals = {
                mid: match.total
                for mid, (terms_m, _) in per_mate.items()
                for match in terms_m
                if match.term.id == tc.term.id and match.total is not None
            }
            term_ranks[tc.term.id] = competition_rank(totals, student.id)
        annual_rank = competition_rank(
            {mid: a.total for mid, (_, a) in per_mate.items() if a.total is not None},
            student.id,
        )

    aspects = await _aspects(db, student.branch_id, sections)
    included_ids = [t.term.id for t in included]
    grades: dict[tuple[int, int], AspectGrade] = {}
    remarks: dict[int, str | None] = {}
    if included_ids:
        for g in await db.scalars(
            select(AspectGrade).where(
                AspectGrade.student_id == student.id, AspectGrade.term_id.in_(included_ids)
            )
        ):
            grades[(g.term_id, g.aspect_id)] = g
        for r in await db.scalars(
            select(TermRemark).where(
                TermRemark.student_id == student.id, TermRemark.term_id.in_(included_ids)
            )
        ):
            remarks[r.term_id] = r.remark

    attendance: AttendanceOut | None = None
    if not family or await settings_service.get_bool(db, _ATTENDANCE_KEY, school_id=school_id):
        attendance = await _attendance(db, student, year)
    guardian = await db.scalar(
        select(Guardian.full_name)
        .where(Guardian.student_id == student.id)
        .order_by(Guardian.is_primary.desc(), Guardian.id)
        .limit(1)
    )
    school_name = await db.scalar(select(School.name).where(School.id == school_id)) or ""
    branch_name = await db.scalar(select(Branch.name).where(Branch.id == student.branch_id)) or ""
    return ReportOut(
        student=ReportStudentOut(
            id=student.id,
            name=student_name(student),
            admission_no=student.admission_no,
            date_of_birth=student.date_of_birth,
            guardian_name=guardian,
        ),
        school_id=school_id,
        school_name=school_name,
        branch_id=student.branch_id,
        branch_name=branch_name,
        academic_year_id=year.id,
        academic_year_name=year.name,
        class_name=class_name,
        section_name=section_name,
        roll_no=enrol.roll_no,
        report_format=report_format,
        aspect_sections=sections,
        pass_percent=ctx.scale.pass_percent,
        grading=_band_out(ctx.scale),
        include_unpublished=show_unpublished,
        show_rank=show_rank,
        principal_name=await settings_service.get_str(
            db, "exams.principal_name", school_id=school_id
        ),
        footer=await settings_service.get_str(db, "exams.report_footer", school_id=school_id),
        attendance=attendance,
        terms=[
            _term_out(tc, ctx, aspects, grades, remarks, term_ranks.get(tc.term.id))
            for tc in included
        ],
        annual=_annual_out(annual, ctx, annual_rank) if included else None,
    )


async def build_progress(
    db: AsyncSession, actor: User, student_id: int, academic_year_id: int
) -> ProgressOut:
    family = _is_family(actor)
    if family:
        await settings_service.require_family_portal(db, actor, _PORTAL_KEY)
    student = await _student_for(db, actor, student_id)
    year = await _year_for(db, student, academic_year_id)
    enrol, _, _ = await _enrolment(db, student, year)
    ctx = await _load_context(
        db,
        school_id=student.school_id,
        branch_id=student.branch_id,
        year_id=year.id,
        class_id=enrol.class_id,
        mate_ids=[student.id],
        show_unpublished=not family,
    )
    included, _ = _calc(ctx, student.id)
    return ProgressOut(
        student_id=student.id,
        academic_year_id=year.id,
        terms=[
            ProgressTermOut(term_id=t.term.id, name=t.term.name, sequence=t.term.sequence)
            for t in included
        ],
        subjects=[
            ProgressSubjectOut(
                subject_id=s.id,
                name=s.name,
                kind=_kind(s),
                points=[
                    ProgressPointOut(term_id=t.term.id, percent=t.subject_percent(s.id))
                    for t in included
                ],
            )
            for s in ctx.subjects
        ],
        totals=[ProgressPointOut(term_id=t.term.id, percent=t.total) for t in included],
    )


async def build_class_summary(
    db: AsyncSession, actor: User, exam_id: int, section_id: int
) -> ClassSummaryOut:
    if actor.role not in RESULT_STAFF_ROLES:
        raise _forbidden()
    exam, term = await common.get_exam(db, actor, exam_id)
    section, klass = await common.get_section(db, actor, section_id, term.branch_id)
    year = await common.year_of(db, term)
    roster = await common.section_roster(db, section, year.id)
    scale = await scale_for(db, term.school_id)
    subjects = list(
        await db.scalars(
            select(Subject)
            .join(ClassSubject, ClassSubject.subject_id == Subject.id)
            .where(ClassSubject.class_id == klass.id)
            .order_by(Subject.name)
        )
    )
    kinds = {s.id: s.kind for s in subjects}
    ids = [s.id for s, _ in roster]
    marks: list[ExamMark] = []
    if ids and subjects:
        marks = list(
            await db.scalars(
                select(ExamMark).where(
                    ExamMark.exam_id == exam.id,
                    ExamMark.student_id.in_(ids),
                    ExamMark.subject_id.in_(list(kinds)),
                )
            )
        )
    exam_ref = ExamRef(
        exam.id, term.id, exam.name, exam.max_marks, exam.weight_percent, exam.published
    )
    # (absent, percent) per subject and per student (scholastic subjects only, for the overall).
    by_subject: dict[int, list[tuple[bool, Decimal]]] = {}
    by_student: dict[int, list[tuple[bool, Decimal]]] = {}
    entered_students: set[int] = set()
    for m in marks:
        if m.marks is None and not m.absent:
            continue
        entered_students.add(m.student_id)
        percent = exam_percent(exam_ref, MarkRef(m.marks, m.absent))
        if percent is None:
            continue
        by_subject.setdefault(m.subject_id, []).append((m.absent, percent))
        if kinds[m.subject_id] == SubjectKind.SCHOLASTIC:
            by_student.setdefault(m.student_id, []).append((m.absent, percent))

    stats: list[ClassSubjectStatOut] = []
    for subject in subjects:
        entries = by_subject.get(subject.id, [])
        present = [p for absent, p in entries if not absent]
        scholastic = subject.kind == SubjectKind.SCHOLASTIC
        stats.append(
            ClassSubjectStatOut(
                subject_id=subject.id,
                name=subject.name,
                kind=subject.kind,
                entered=len(entries),
                absent=sum(1 for absent, _ in entries if absent),
                average_percent=q2(sum(present, Decimal(0)) / Decimal(len(present)))
                if present
                else None,
                highest_percent=max(present) if present else None,
                lowest_percent=min(present) if present else None,
                fail_count=sum(1 for p in present if scholastic and p < scale.pass_percent),
            )
        )

    student_avgs: list[Decimal] = []
    fail_students = 0
    for rows in by_student.values():
        # An absent student counts 0 in the overall average, and is not counted as a fail.
        student_avgs.append(q2(sum((p for _, p in rows), Decimal(0)) / Decimal(len(rows))))
        if any(not absent and p < scale.pass_percent for absent, p in rows):
            fail_students += 1
    return ClassSummaryOut(
        exam=ExamRefOut(
            id=exam.id,
            name=exam.name,
            max_marks=exam.max_marks,
            published=exam.published,
            locked=exam.locked,
            term_id=term.id,
            term_name=term.name,
        ),
        section=SectionRefOut(
            id=section.id, name=section.name, class_id=klass.id, class_name=klass.name
        ),
        pass_percent=scale.pass_percent,
        students_count=len(roster),
        entered_count=len(entered_students),
        subjects=stats,
        overall=ClassOverallOut(
            average_percent=q2(sum(student_avgs, Decimal(0)) / Decimal(len(student_avgs)))
            if student_avgs
            else None,
            highest_percent=max(student_avgs) if student_avgs else None,
            lowest_percent=min(student_avgs) if student_avgs else None,
            fail_count=fail_students,
        ),
    )


async def report_card_pdf(
    db: AsyncSession,
    actor: User,
    student_id: int,
    academic_year_id: int,
    *,
    include_unpublished: bool,
    format_override: str | None,
) -> bytes:
    """The report card as PDF. The download is audited (ids and the layout only)."""
    report = await build_report(
        db,
        actor,
        student_id,
        academic_year_id,
        include_unpublished=include_unpublished,
        format_override=format_override,
    )
    logo = await db.scalar(select(SchoolLogo.data).where(SchoolLogo.school_id == report.school_id))
    layout: Literal["cbse", "hpc"] = "hpc" if report.report_format == "hpc" else "cbse"
    pdf = build_report_pdf(report, logo, layout)
    await audit.record(
        db,
        actor,
        "exam.report_card.exported",
        "student",
        student_id,
        school_id=report.school_id,
        branch_id=report.branch_id,
        detail={"academic_year_id": academic_year_id, "layout": layout},
        commit=True,
    )
    return pdf
