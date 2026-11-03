"""Exam configuration: terms, subjects, class subjects, exams, the grading scale and report aspects.

Writes need a configuring role (school owner, management, headmaster); reads also allow teachers
and clerks of the branch. Every write is audited with ids and field names only.
"""

from decimal import Decimal

from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.tenant import scope_exams, scope_grading
from app.modules.academics.models import AcademicYear, SchoolClass
from app.modules.audit import service as audit
from app.modules.exams import common
from app.modules.exams.calc import BandRef, ScaleRef
from app.modules.exams.common import CONFIG_ROLES, conflict, not_found, unprocessable
from app.modules.exams.models import (
    AspectSection,
    ClassSubject,
    Exam,
    ExamMark,
    ExamTerm,
    GradeBand,
    GradeScale,
    ReportAspect,
    Subject,
)
from app.modules.exams.schemas import (
    AspectIn,
    AspectOut,
    AspectPatch,
    BandIn,
    BandOut,
    ClassSubjectsOut,
    ClassSubjectsPut,
    ExamIn,
    ExamOut,
    ExamPatch,
    GradingOut,
    GradingPut,
    SubjectIn,
    SubjectOut,
    SubjectPatch,
    TermIn,
    TermOut,
    TermPatch,
)
from app.modules.users.models import User

DEFAULT_SCALE_NAME = "CBSE 9-point"
# Seed for the default scale only (min percent, grade, grade point). After creation all grading
# lives in the grade_bands table and is edited through the Grading endpoint.
_CBSE_SEED: tuple[tuple[int, str, str], ...] = (
    (91, "A1", "10"),
    (81, "A2", "9"),
    (71, "B1", "8"),
    (61, "B2", "7"),
    (51, "C1", "6"),
    (41, "C2", "5"),
    (33, "D", "4"),
    (21, "E1", "0"),
    (0, "E2", "0"),
)
DEFAULT_PASS_PERCENT = 33


def _require_config(actor: User) -> None:
    common.require_role(actor, CONFIG_ROLES)


def _changed(data: object) -> list[str]:
    fields: set[str] = getattr(data, "model_fields_set", set())
    return sorted(fields)


def term_out(term: ExamTerm) -> TermOut:
    return TermOut(
        id=term.id,
        branch_id=term.branch_id,
        academic_year_id=term.academic_year_id,
        name=term.name,
        sequence=term.sequence,
        weight_percent=term.weight_percent,
    )


def subject_out(subject: Subject) -> SubjectOut:
    return SubjectOut(
        id=subject.id,
        branch_id=subject.branch_id,
        name=subject.name,
        code=subject.code,
        kind=subject.kind,
        active=subject.active,
    )


def exam_out(exam: Exam, term_name: str) -> ExamOut:
    return ExamOut(
        id=exam.id,
        branch_id=exam.branch_id,
        term_id=exam.term_id,
        term_name=term_name,
        name=exam.name,
        max_marks=exam.max_marks,
        weight_percent=exam.weight_percent,
        published=exam.published,
        locked=exam.locked,
    )


def aspect_out(aspect: ReportAspect) -> AspectOut:
    return AspectOut(
        id=aspect.id,
        branch_id=aspect.branch_id,
        section=aspect.section,
        name=aspect.name,
        active=aspect.active,
        sequence=aspect.sequence,
    )


async def _commit_or_conflict(db: AsyncSession, detail: str, code: str) -> None:
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        raise conflict(detail, code) from None


# ---------------------------------------------------------------- terms


async def list_terms(
    db: AsyncSession, actor: User, branch_id: int | None, academic_year_id: int | None
) -> list[TermOut]:
    stmt = scope_exams(select(ExamTerm), ExamTerm, actor)
    scoped_branch = await common.branch_filter(db, actor, branch_id)
    if scoped_branch is not None:
        stmt = stmt.where(ExamTerm.branch_id == scoped_branch)
    if academic_year_id is not None:
        stmt = stmt.where(ExamTerm.academic_year_id == academic_year_id)
    rows = await db.scalars(
        stmt.order_by(ExamTerm.academic_year_id.desc(), ExamTerm.sequence, ExamTerm.id).limit(200)
    )
    return [term_out(t) for t in rows]


async def create_term(
    db: AsyncSession, actor: User, branch_id: int | None, data: TermIn
) -> TermOut:
    _require_config(actor)
    branch = await common.resolve_branch(db, actor, branch_id)
    year: AcademicYear | None = await db.scalar(
        select(AcademicYear).where(
            AcademicYear.id == data.academic_year_id, AcademicYear.school_id == branch.school_id
        )
    )
    if year is None:
        raise unprocessable("Academic year not found", "invalid_year")
    term = ExamTerm(
        school_id=branch.school_id,
        branch_id=branch.id,
        academic_year_id=year.id,
        name=data.name,
        sequence=data.sequence,
        weight_percent=data.weight_percent,
    )
    db.add(term)
    await _commit_or_conflict(db, "A term with this name already exists", "term_exists")
    await audit.record(
        db, actor, "exam.term.created", "exam_term", term.id, detail={"academic_year_id": year.id}
    )
    await db.commit()
    return term_out(term)


async def update_term(db: AsyncSession, actor: User, term_id: int, data: TermPatch) -> TermOut:
    _require_config(actor)
    term = await common.get_term(db, actor, term_id)
    if data.name is not None:
        term.name = data.name
    if data.sequence is not None:
        term.sequence = data.sequence
    if data.weight_percent is not None:
        term.weight_percent = data.weight_percent
    await _commit_or_conflict(db, "A term with this name already exists", "term_exists")
    await audit.record(
        db, actor, "exam.term.updated", "exam_term", term.id, detail={"fields": _changed(data)}
    )
    await db.commit()
    return term_out(term)


# ---------------------------------------------------------------- subjects


async def list_subjects(
    db: AsyncSession, actor: User, branch_id: int | None, include_inactive: bool
) -> list[SubjectOut]:
    stmt = scope_exams(select(Subject), Subject, actor)
    scoped_branch = await common.branch_filter(db, actor, branch_id)
    if scoped_branch is not None:
        stmt = stmt.where(Subject.branch_id == scoped_branch)
    if not include_inactive:
        stmt = stmt.where(Subject.active.is_(True))
    rows = await db.scalars(stmt.order_by(Subject.name, Subject.id).limit(300))
    return [subject_out(s) for s in rows]


async def create_subject(
    db: AsyncSession, actor: User, branch_id: int | None, data: SubjectIn
) -> SubjectOut:
    _require_config(actor)
    branch = await common.resolve_branch(db, actor, branch_id)
    subject = Subject(
        school_id=branch.school_id,
        branch_id=branch.id,
        name=data.name,
        code=(data.code or None),
        kind=data.kind,
        active=data.active,
    )
    db.add(subject)
    await _commit_or_conflict(db, "A subject with this name already exists", "subject_exists")
    await audit.record(
        db, actor, "exam.subject.created", "subject", subject.id, detail={"kind": data.kind.value}
    )
    await db.commit()
    return subject_out(subject)


async def update_subject(
    db: AsyncSession, actor: User, subject_id: int, data: SubjectPatch
) -> SubjectOut:
    _require_config(actor)
    subject: Subject | None = await db.scalar(
        scope_exams(select(Subject), Subject, actor).where(Subject.id == subject_id)
    )
    if subject is None:
        raise not_found("Subject")
    if data.name is not None:
        subject.name = data.name
    if "code" in data.model_fields_set:
        subject.code = data.code or None
    if data.kind is not None:
        subject.kind = data.kind
    if data.active is not None:
        subject.active = data.active
    await _commit_or_conflict(db, "A subject with this name already exists", "subject_exists")
    await audit.record(
        db, actor, "exam.subject.updated", "subject", subject.id, detail={"fields": _changed(data)}
    )
    await db.commit()
    return subject_out(subject)


# ---------------------------------------------------------------- class subjects


async def class_subjects(db: AsyncSession, actor: User, class_id: int) -> ClassSubjectsOut:
    klass: SchoolClass | None = await db.scalar(
        scope_exams(select(SchoolClass), SchoolClass, actor).where(SchoolClass.id == class_id)
    )
    if klass is None:
        raise not_found("Class")
    rows = await db.scalars(
        select(Subject)
        .join(ClassSubject, ClassSubject.subject_id == Subject.id)
        .where(ClassSubject.class_id == klass.id)
        .order_by(Subject.kind, Subject.name)
    )
    return ClassSubjectsOut(
        class_id=klass.id,
        class_name=klass.name,
        subjects=[subject_out(s) for s in rows],
    )


async def replace_class_subjects(
    db: AsyncSession, actor: User, data: ClassSubjectsPut
) -> ClassSubjectsOut:
    _require_config(actor)
    klass: SchoolClass | None = await db.scalar(
        scope_exams(select(SchoolClass), SchoolClass, actor).where(SchoolClass.id == data.class_id)
    )
    if klass is None:
        raise not_found("Class")
    wanted = set(data.subject_ids)
    if len(wanted) != len(data.subject_ids):
        raise unprocessable("A subject is listed twice", "duplicate_subject")
    if wanted:
        found = (
            await db.scalars(
                select(Subject).where(
                    Subject.id.in_(wanted),
                    Subject.branch_id == klass.branch_id,
                    Subject.school_id == klass.school_id,
                )
            )
        ).all()
        if len(found) != len(wanted):
            raise unprocessable("Subject does not belong to this branch", "invalid_subject")
        if any(not s.active for s in found):
            raise unprocessable("Inactive subjects cannot be added to a class", "subject_inactive")
    current = set(
        (
            await db.scalars(
                select(ClassSubject.subject_id).where(ClassSubject.class_id == klass.id)
            )
        ).all()
    )
    removed = current - wanted
    if removed:
        await db.execute(
            delete(ClassSubject).where(
                ClassSubject.class_id == klass.id, ClassSubject.subject_id.in_(removed)
            )
        )
    for subject_id in sorted(wanted - current):
        db.add(
            ClassSubject(
                school_id=klass.school_id,
                branch_id=klass.branch_id,
                class_id=klass.id,
                subject_id=subject_id,
            )
        )
    await db.flush()
    await audit.record(
        db,
        actor,
        "exam.class_subjects.replaced",
        "class",
        klass.id,
        detail={"subjects": len(wanted), "added": len(wanted - current), "removed": len(removed)},
    )
    await db.commit()
    return await class_subjects(db, actor, klass.id)


# ---------------------------------------------------------------- exams


async def list_exams(
    db: AsyncSession,
    actor: User,
    term_id: int | None,
    branch_id: int | None,
) -> list[ExamOut]:
    stmt = scope_exams(
        select(Exam, ExamTerm.name).join(ExamTerm, ExamTerm.id == Exam.term_id), Exam, actor
    )
    scoped_branch = await common.branch_filter(db, actor, branch_id)
    if scoped_branch is not None:
        stmt = stmt.where(Exam.branch_id == scoped_branch)
    if term_id is not None:
        stmt = stmt.where(Exam.term_id == term_id)
    rows = await db.execute(stmt.order_by(ExamTerm.sequence, Exam.name, Exam.id).limit(300))
    return [exam_out(exam, name) for exam, name in rows.all()]


async def create_exam(db: AsyncSession, actor: User, data: ExamIn) -> ExamOut:
    _require_config(actor)
    term = await common.get_term(db, actor, data.term_id)
    exam = Exam(
        school_id=term.school_id,
        branch_id=term.branch_id,
        term_id=term.id,
        name=data.name,
        max_marks=data.max_marks,
        weight_percent=data.weight_percent,
        published=data.published,
        locked=data.locked,
    )
    db.add(exam)
    await _commit_or_conflict(
        db, "An exam with this name already exists in the term", "exam_exists"
    )
    await audit.record(db, actor, "exam.created", "exam", exam.id, detail={"term_id": term.id})
    await db.commit()
    return exam_out(exam, term.name)


async def update_exam(db: AsyncSession, actor: User, exam_id: int, data: ExamPatch) -> ExamOut:
    _require_config(actor)
    exam, term = await common.get_exam(db, actor, exam_id)
    effective_locked = exam.locked if data.locked is None else data.locked
    structural = {"max_marks", "weight_percent"} & data.model_fields_set
    if effective_locked and structural:
        raise conflict("The exam is locked", "exam_locked")
    if data.max_marks is not None and data.max_marks != exam.max_marks:
        highest = await db.scalar(
            select(func.max(ExamMark.marks)).where(
                ExamMark.exam_id == exam.id, ExamMark.marks.is_not(None)
            )
        )
        if highest is not None and Decimal(highest) > Decimal(data.max_marks):
            raise unprocessable("Some marks are above the new maximum", "max_marks_below_marks")
    if data.name is not None:
        exam.name = data.name
    if data.max_marks is not None:
        exam.max_marks = data.max_marks
    if data.weight_percent is not None:
        exam.weight_percent = data.weight_percent
    publish_changed = data.published is not None and data.published != exam.published
    lock_changed = data.locked is not None and data.locked != exam.locked
    if data.published is not None:
        exam.published = data.published
    if data.locked is not None:
        exam.locked = data.locked
    await _commit_or_conflict(
        db, "An exam with this name already exists in the term", "exam_exists"
    )
    await audit.record(
        db, actor, "exam.updated", "exam", exam.id, detail={"fields": _changed(data)}
    )
    if publish_changed:
        await audit.record(
            db, actor, "exam.published" if exam.published else "exam.unpublished", "exam", exam.id
        )
    if lock_changed:
        await audit.record(
            db, actor, "exam.locked" if exam.locked else "exam.unlocked", "exam", exam.id
        )
    await db.commit()
    return exam_out(exam, term.name)


# ---------------------------------------------------------------- grading


def _scale_ref(scale: GradeScale, bands: list[GradeBand]) -> ScaleRef:
    return ScaleRef(
        pass_percent=scale.pass_percent,
        bands=tuple(
            BandRef(b.min_percent, b.grade, b.grade_point, b.remark)
            for b in sorted(bands, key=lambda b: b.min_percent, reverse=True)
        ),
    )


async def _bands(db: AsyncSession, scale_id: int) -> list[GradeBand]:
    rows = await db.scalars(
        select(GradeBand).where(GradeBand.scale_id == scale_id).order_by(GradeBand.min_percent)
    )
    return list(rows)


async def default_scale(
    db: AsyncSession, school_id: int, actor: User | None = None
) -> tuple[GradeScale, list[GradeBand]]:
    """The school's default grading scale. The CBSE seed is created on first use."""
    scale: GradeScale | None = await db.scalar(
        select(GradeScale).where(GradeScale.school_id == school_id, GradeScale.is_default.is_(True))
    )
    if scale is None:
        scale = GradeScale(
            school_id=school_id,
            name=DEFAULT_SCALE_NAME,
            is_default=True,
            pass_percent=DEFAULT_PASS_PERCENT,
        )
        db.add(scale)
        try:
            await db.flush()
        except IntegrityError:
            # Another request created it first; the partial unique index keeps one default.
            await db.rollback()
            scale = await db.scalar(
                select(GradeScale).where(
                    GradeScale.school_id == school_id, GradeScale.is_default.is_(True)
                )
            )
            if scale is None:  # pragma: no cover - the index and the select cannot disagree
                raise
            return scale, await _bands(db, scale.id)
        for min_percent, grade, point in _CBSE_SEED:
            db.add(
                GradeBand(
                    scale_id=scale.id,
                    min_percent=min_percent,
                    grade=grade,
                    grade_point=Decimal(point),
                    remark=None,
                )
            )
        await db.flush()
        await audit.record(
            db,
            actor,
            "exam.grading.default_created",
            "grade_scale",
            scale.id,
            school_id=school_id,
            commit=True,
        )
        return scale, await _bands(db, scale.id)
    return scale, await _bands(db, scale.id)


async def scale_for(db: AsyncSession, school_id: int) -> ScaleRef:
    scale, bands = await default_scale(db, school_id)
    return _scale_ref(scale, bands)


def _grading_out(scale: GradeScale, bands: list[GradeBand]) -> GradingOut:
    return GradingOut(
        id=scale.id,
        name=scale.name,
        is_default=scale.is_default,
        pass_percent=scale.pass_percent,
        bands=[
            BandOut(
                min_percent=b.min_percent,
                grade=b.grade,
                grade_point=b.grade_point,
                remark=b.remark,
            )
            for b in sorted(bands, key=lambda b: b.min_percent, reverse=True)
        ],
    )


def _validate_bands(bands: list[BandIn]) -> None:
    """Bands must start at 0, have distinct minimums and labels, and grade points must not rise
    as the marks fall. Problems are reported as 422 with a plain message."""
    minimums = [b.min_percent for b in bands]
    if len(set(minimums)) != len(minimums):
        raise unprocessable("Each band needs its own minimum percent", "invalid_grading")
    if 0 not in minimums:
        raise unprocessable("The lowest band must start at 0 percent", "invalid_grading")
    labels = [b.grade.casefold() for b in bands]
    if len(set(labels)) != len(labels):
        raise unprocessable("Grade labels must be unique", "invalid_grading")
    previous: Decimal | None = None
    for band in sorted(bands, key=lambda b: b.min_percent, reverse=True):
        point = band.grade_point
        if point is not None and point != point.quantize(Decimal("0.1")):
            raise unprocessable("Grade points take one decimal place at most", "invalid_grading")
        if point is not None:
            if previous is not None and point > previous:
                raise unprocessable(
                    "Grade points must not rise as the marks fall", "invalid_grading"
                )
            previous = point


async def get_grading(db: AsyncSession, actor: User) -> GradingOut:
    if actor.school_id is None:
        raise not_found("Grading scale")
    scale: GradeScale | None = await db.scalar(
        scope_grading(select(GradeScale), actor).where(GradeScale.is_default.is_(True))
    )
    if scale is None:
        scale, bands = await default_scale(db, actor.school_id, actor)
    else:
        bands = await _bands(db, scale.id)
    return _grading_out(scale, bands)


async def replace_grading(db: AsyncSession, actor: User, data: GradingPut) -> GradingOut:
    _require_config(actor)
    if actor.school_id is None:
        raise not_found("Grading scale")
    _validate_bands(data.bands)
    scale, _ = await default_scale(db, actor.school_id, actor)
    scale.pass_percent = data.pass_percent
    if data.name is not None:
        scale.name = data.name
    await db.execute(delete(GradeBand).where(GradeBand.scale_id == scale.id))
    await db.flush()
    for band in data.bands:
        db.add(
            GradeBand(
                scale_id=scale.id,
                min_percent=band.min_percent,
                grade=band.grade,
                grade_point=band.grade_point,
                remark=band.remark or None,
            )
        )
    await _commit_or_conflict(db, "A grading scale with this name already exists", "scale_exists")
    await audit.record(
        db,
        actor,
        "exam.grading.replaced",
        "grade_scale",
        scale.id,
        detail={"bands": len(data.bands), "pass_percent": data.pass_percent},
    )
    await db.commit()
    return _grading_out(scale, await _bands(db, scale.id))


# ---------------------------------------------------------------- report aspects


async def list_aspects(db: AsyncSession, actor: User, branch_id: int | None) -> list[AspectOut]:
    stmt = scope_exams(select(ReportAspect), ReportAspect, actor)
    scoped_branch = await common.branch_filter(db, actor, branch_id)
    if scoped_branch is not None:
        stmt = stmt.where(ReportAspect.branch_id == scoped_branch)
    rows = await db.scalars(
        stmt.order_by(ReportAspect.section, ReportAspect.sequence, ReportAspect.name).limit(200)
    )
    return [aspect_out(a) for a in rows]


async def create_aspect(
    db: AsyncSession, actor: User, branch_id: int | None, data: AspectIn
) -> AspectOut:
    _require_config(actor)
    branch = await common.resolve_branch(db, actor, branch_id)
    aspect = ReportAspect(
        school_id=branch.school_id,
        branch_id=branch.id,
        section=data.section,
        name=data.name,
        active=data.active,
        sequence=data.sequence,
    )
    db.add(aspect)
    await _commit_or_conflict(db, "An aspect with this name already exists", "aspect_exists")
    await audit.record(
        db,
        actor,
        "exam.aspect.created",
        "report_aspect",
        aspect.id,
        detail={"section": data.section.value},
    )
    await db.commit()
    return aspect_out(aspect)


async def update_aspect(
    db: AsyncSession, actor: User, aspect_id: int, data: AspectPatch
) -> AspectOut:
    _require_config(actor)
    aspect: ReportAspect | None = await db.scalar(
        scope_exams(select(ReportAspect), ReportAspect, actor).where(ReportAspect.id == aspect_id)
    )
    if aspect is None:
        raise not_found("Aspect")
    if data.name is not None:
        aspect.name = data.name
    if data.active is not None:
        aspect.active = data.active
    if data.sequence is not None:
        aspect.sequence = data.sequence
    await _commit_or_conflict(db, "An aspect with this name already exists", "aspect_exists")
    await audit.record(
        db,
        actor,
        "exam.aspect.updated",
        "report_aspect",
        aspect.id,
        detail={"fields": _changed(data)},
    )
    await db.commit()
    return aspect_out(aspect)


def configured_sections(raw: str | None) -> list[AspectSection]:
    """The aspect sections a school shows on report cards, in the order they are listed."""
    if not raw:
        return []
    out: list[AspectSection] = []
    for part in raw.split(","):
        name = part.strip()
        if not name:
            continue
        section = AspectSection(name)
        if section not in out:
            out.append(section)
    return out
