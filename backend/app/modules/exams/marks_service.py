"""Marks entry, aspect grades and term remarks for one section.

Writes are all-or-nothing: every row is checked first, and if any row is wrong nothing is saved
and the response is 422 with one {row, message} entry per bad row (rows are 1-based, in the
order sent). A locked exam refuses mark writes with 409 `exam_locked`. Audit rows carry ids and
counts only, never marks or remarks.
"""

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ApiError
from app.modules.audit import service as audit
from app.modules.exams import common
from app.modules.exams.common import (
    MARK_ROLES,
    conflict,
    get_exam,
    get_section,
    get_subject,
    get_term,
    section_roster,
    student_name,
    unprocessable,
    year_of,
)
from app.modules.exams.config_service import aspect_out
from app.modules.exams.models import (
    AspectGrade,
    AspectGradeValue,
    ClassSubject,
    Exam,
    ExamMark,
    ExamTerm,
    ReportAspect,
    TermRemark,
)
from app.modules.exams.schemas import (
    AspectCellOut,
    AspectGradesOut,
    AspectGradesPut,
    AspectStudentOut,
    ExamRefOut,
    MarksOut,
    MarksPut,
    MarkStudentOut,
    SectionRefOut,
    SubjectRefOut,
    TermRemarksOut,
    TermRemarksPut,
    TermRemarkStudentOut,
)
from app.modules.students.models import Enrollment, Student
from app.modules.users.models import User

_CENT = Decimal("0.01")


def _row_errors(errors: list[tuple[int, str]]) -> ApiError:
    return ApiError(
        422,
        [{"row": row, "message": message} for row, message in errors],
        "row_errors",
    )


async def _section_context(
    db: AsyncSession, actor: User, term: ExamTerm, section_id: int
) -> tuple[SectionRefOut, list[tuple[Student, Enrollment]]]:
    section, klass = await get_section(db, actor, section_id, term.branch_id)
    year = await year_of(db, term)
    roster = await section_roster(db, section, year.id)
    ref = SectionRefOut(id=section.id, name=section.name, class_id=klass.id, class_name=klass.name)
    return ref, roster


async def _require_class_subject(db: AsyncSession, class_id: int, subject_id: int) -> None:
    found = await db.scalar(
        select(ClassSubject.id).where(
            ClassSubject.class_id == class_id, ClassSubject.subject_id == subject_id
        )
    )
    if found is None:
        raise unprocessable("This subject is not taught in the class", "subject_not_for_class")


# ---------------------------------------------------------------- marks


async def get_marks(
    db: AsyncSession, actor: User, exam_id: int, section_id: int, subject_id: int
) -> MarksOut:
    exam, term = await get_exam(db, actor, exam_id)
    section, roster = await _section_context(db, actor, term, section_id)
    subject = await get_subject(db, actor, subject_id, term.branch_id)
    await _require_class_subject(db, section.class_id, subject.id)
    ids = [s.id for s, _ in roster]
    marks = {
        m.student_id: m
        for m in await db.scalars(
            select(ExamMark).where(
                ExamMark.exam_id == exam.id,
                ExamMark.subject_id == subject.id,
                ExamMark.student_id.in_(ids) if ids else ExamMark.id.is_(None),
            )
        )
    }
    students = []
    for student, enrol in roster:
        mark = marks.get(student.id)
        students.append(
            MarkStudentOut(
                student_id=student.id,
                name=student_name(student),
                roll_no=enrol.roll_no,
                marks=mark.marks if mark else None,
                absent=bool(mark.absent) if mark else False,
            )
        )
    return MarksOut(
        exam=_exam_ref(exam, term),
        subject=SubjectRefOut(id=subject.id, name=subject.name, kind=subject.kind),
        section=section,
        students=students,
    )


def _exam_ref(exam: Exam, term: ExamTerm) -> ExamRefOut:
    return ExamRefOut(
        id=exam.id,
        name=exam.name,
        max_marks=exam.max_marks,
        published=exam.published,
        locked=exam.locked,
        term_id=term.id,
        term_name=term.name,
    )


def _check_mark_row(
    row_no: int,
    row_marks: Decimal | None,
    absent: bool,
    max_marks: int,
    errors: list[tuple[int, str]],
) -> None:
    if row_marks is None:
        return
    if absent:
        errors.append((row_no, "An absent student cannot have marks"))
        return
    if row_marks < 0 or row_marks > Decimal(max_marks):
        errors.append((row_no, f"Marks must be between 0 and {max_marks}"))
    elif row_marks != row_marks.quantize(_CENT):
        errors.append((row_no, "Marks take two decimal places at most"))


async def put_marks(db: AsyncSession, actor: User, data: MarksPut) -> MarksOut:
    common.require_role(actor, MARK_ROLES)
    exam, term = await get_exam(db, actor, data.exam_id)
    if exam.locked:
        raise conflict("The exam is locked; marks cannot change", "exam_locked")
    section, roster = await _section_context(db, actor, term, data.section_id)
    subject = await get_subject(db, actor, data.subject_id, term.branch_id)
    await _require_class_subject(db, section.class_id, subject.id)

    roster_ids = {s.id for s, _ in roster}
    errors: list[tuple[int, str]] = []
    seen: set[int] = set()
    for number, row in enumerate(data.rows, start=1):
        if row.student_id in seen:
            errors.append((number, "This student is listed twice"))
            continue
        seen.add(row.student_id)
        if row.student_id not in roster_ids:
            errors.append((number, "This student is not in this section for the year"))
            continue
        _check_mark_row(number, row.marks, row.absent, exam.max_marks, errors)
    if errors:
        raise _row_errors(errors)

    existing = {
        m.student_id: m
        for m in await db.scalars(
            select(ExamMark).where(
                ExamMark.exam_id == exam.id,
                ExamMark.subject_id == subject.id,
                ExamMark.student_id.in_(seen),
            )
        )
    }
    changed = 0
    for row in data.rows:
        quantized = None if row.marks is None else row.marks.quantize(_CENT)
        mark = existing.get(row.student_id)
        if mark is None:
            if quantized is None and not row.absent:
                continue  # nothing to clear and nothing to record
            db.add(
                ExamMark(
                    school_id=term.school_id,
                    branch_id=term.branch_id,
                    exam_id=exam.id,
                    student_id=row.student_id,
                    subject_id=subject.id,
                    marks=quantized,
                    absent=row.absent,
                    entered_by=actor.id,
                )
            )
            changed += 1
            continue
        if mark.marks == quantized and mark.absent == row.absent:
            continue
        mark.marks = quantized
        mark.absent = row.absent
        mark.entered_by = actor.id
        changed += 1
    await db.flush()
    await audit.record(
        db,
        actor,
        "exam.marks.saved",
        "exam",
        exam.id,
        detail={
            "subject_id": subject.id,
            "section_id": section.id,
            "rows": len(data.rows),
            "changed": changed,
        },
    )
    await db.commit()
    return await get_marks(db, actor, exam.id, section.id, subject.id)


# ---------------------------------------------------------------- aspect grades


async def _active_aspects(db: AsyncSession, branch_id: int) -> list[ReportAspect]:
    rows = await db.scalars(
        select(ReportAspect)
        .where(ReportAspect.branch_id == branch_id, ReportAspect.active.is_(True))
        .order_by(ReportAspect.section, ReportAspect.sequence, ReportAspect.name)
    )
    return list(rows)


async def get_aspect_grades(
    db: AsyncSession, actor: User, term_id: int, section_id: int
) -> AspectGradesOut:
    term = await get_term(db, actor, term_id)
    section, roster = await _section_context(db, actor, term, section_id)
    aspects = await _active_aspects(db, term.branch_id)
    ids = [s.id for s, _ in roster]
    grades: dict[tuple[int, int], AspectGrade] = {}
    if ids:
        for row in await db.scalars(
            select(AspectGrade).where(
                AspectGrade.term_id == term.id, AspectGrade.student_id.in_(ids)
            )
        ):
            grades[(row.student_id, row.aspect_id)] = row
    students = []
    for student, enrol in roster:
        cells = []
        for aspect in aspects:
            found = grades.get((student.id, aspect.id))
            cells.append(
                AspectCellOut(
                    aspect_id=aspect.id,
                    grade=found.grade if found else None,
                    remark=found.remark if found else None,
                )
            )
        students.append(
            AspectStudentOut(
                student_id=student.id,
                name=student_name(student),
                roll_no=enrol.roll_no,
                grades=cells,
            )
        )
    return AspectGradesOut(
        term_id=term.id,
        term_name=term.name,
        section=section,
        aspects=[aspect_out(a) for a in aspects],
        students=students,
    )


async def put_aspect_grades(
    db: AsyncSession, actor: User, data: AspectGradesPut
) -> AspectGradesOut:
    common.require_role(actor, MARK_ROLES)
    term = await get_term(db, actor, data.term_id)
    _, roster = await _section_context(db, actor, term, data.section_id)
    aspects = {a.id: a for a in await _active_aspects(db, term.branch_id)}
    wanted_aspects = {row.aspect_id for row in data.rows}
    if not wanted_aspects <= set(aspects):
        raise unprocessable("An aspect is missing or not active", "invalid_aspect")
    roster_ids = {s.id for s, _ in roster}
    errors: list[tuple[int, str]] = []
    seen: set[tuple[int, int]] = set()
    for number, row in enumerate(data.rows, start=1):
        key = (row.student_id, row.aspect_id)
        if key in seen:
            errors.append((number, "This student and aspect are listed twice"))
            continue
        seen.add(key)
        if row.student_id not in roster_ids:
            errors.append((number, "This student is not in this section for the year"))
        elif row.grade is None and row.remark:
            errors.append((number, "A remark needs a grade"))
    if errors:
        raise _row_errors(errors)

    existing = {
        (g.student_id, g.aspect_id): g
        for g in await db.scalars(
            select(AspectGrade).where(
                AspectGrade.term_id == term.id,
                AspectGrade.student_id.in_({r.student_id for r in data.rows}),
            )
        )
    }
    changed = 0
    for row in data.rows:
        key = (row.student_id, row.aspect_id)
        found = existing.get(key)
        if row.grade is None:
            if found is not None:
                await db.delete(found)
                changed += 1
            continue
        remark = row.remark or None
        if found is None:
            db.add(
                AspectGrade(
                    school_id=term.school_id,
                    branch_id=term.branch_id,
                    term_id=term.id,
                    student_id=row.student_id,
                    aspect_id=row.aspect_id,
                    grade=AspectGradeValue(row.grade),
                    remark=remark,
                    entered_by=actor.id,
                )
            )
            changed += 1
        elif found.grade != row.grade or found.remark != remark:
            found.grade = AspectGradeValue(row.grade)
            found.remark = remark
            found.entered_by = actor.id
            changed += 1
    await db.flush()
    await audit.record(
        db,
        actor,
        "exam.aspects.saved",
        "exam_term",
        term.id,
        detail={"section_id": data.section_id, "rows": len(data.rows), "changed": changed},
    )
    await db.commit()
    return await get_aspect_grades(db, actor, term.id, data.section_id)


# ---------------------------------------------------------------- term remarks


async def get_term_remarks(
    db: AsyncSession, actor: User, term_id: int, section_id: int
) -> TermRemarksOut:
    term = await get_term(db, actor, term_id)
    section, roster = await _section_context(db, actor, term, section_id)
    ids = [s.id for s, _ in roster]
    remarks: dict[int, str | None] = {}
    if ids:
        for row in await db.scalars(
            select(TermRemark).where(TermRemark.term_id == term.id, TermRemark.student_id.in_(ids))
        ):
            remarks[row.student_id] = row.remark
    return TermRemarksOut(
        term_id=term.id,
        term_name=term.name,
        section=section,
        students=[
            TermRemarkStudentOut(
                student_id=s.id,
                name=student_name(s),
                roll_no=e.roll_no,
                remark=remarks.get(s.id),
            )
            for s, e in roster
        ],
    )


async def put_term_remarks(
    db: AsyncSession, actor: User, term_id: int, section_id: int, data: TermRemarksPut
) -> TermRemarksOut:
    common.require_role(actor, MARK_ROLES)
    term = await get_term(db, actor, term_id)
    _, roster = await _section_context(db, actor, term, section_id)
    roster_ids = {s.id for s, _ in roster}
    errors: list[tuple[int, str]] = []
    seen: set[int] = set()
    for number, row in enumerate(data.rows, start=1):
        if row.student_id in seen:
            errors.append((number, "This student is listed twice"))
            continue
        seen.add(row.student_id)
        if row.student_id not in roster_ids:
            errors.append((number, "This student is not in this section for the year"))
    if errors:
        raise _row_errors(errors)
    existing = {
        r.student_id: r
        for r in await db.scalars(
            select(TermRemark).where(TermRemark.term_id == term.id, TermRemark.student_id.in_(seen))
        )
    }
    changed = 0
    for row in data.rows:
        remark = row.remark or None
        found = existing.get(row.student_id)
        if found is None:
            if remark is None:
                continue
            db.add(
                TermRemark(
                    school_id=term.school_id,
                    branch_id=term.branch_id,
                    term_id=term.id,
                    student_id=row.student_id,
                    remark=remark,
                    entered_by=actor.id,
                )
            )
            changed += 1
        elif found.remark != remark:
            found.remark = remark
            found.entered_by = actor.id
            changed += 1
    await db.flush()
    await audit.record(
        db,
        actor,
        "exam.term_remarks.saved",
        "exam_term",
        term.id,
        detail={"section_id": section_id, "rows": len(data.rows), "changed": changed},
    )
    await db.commit()
    return await get_term_remarks(db, actor, term.id, section_id)
