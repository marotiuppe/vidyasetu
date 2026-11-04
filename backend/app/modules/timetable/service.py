"""Timetable: period slots of a branch and the weekly entries of each section.

Writes need a configuring role (school owner, management, headmaster). Teachers and clerks read
their branch; teachers also read their own week. Parents and students read only the week of their
own child (or themselves) through the student scope. Writes are audited with ids only.
"""

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.tenant import scope_exams, scope_students, scope_users
from app.modules.academics.models import SchoolClass, Section
from app.modules.audit import service as audit
from app.modules.exams.common import resolve_branch
from app.modules.exams.models import Subject
from app.modules.students.models import Enrollment, Student
from app.modules.timetable import common
from app.modules.timetable.common import CONFIG_ROLES, FAMILY_ROLES, conflict, not_found
from app.modules.timetable.models import PeriodSlot, TimetableEntry
from app.modules.timetable.schemas import (
    EntryOut,
    EntryPut,
    PeriodIn,
    PeriodOut,
    PeriodPatch,
    PersonEntryOut,
    SectionRef,
    SectionWeekOut,
    StudentRef,
    StudentWeekOut,
    TeacherRef,
    TeacherWeekOut,
)
from app.modules.users.models import Role, User


def _require_config(actor: User) -> None:
    common.require_role(actor, CONFIG_ROLES)


def period_out(p: PeriodSlot) -> PeriodOut:
    return PeriodOut(
        id=p.id,
        branch_id=p.branch_id,
        name=p.name,
        sequence=p.sequence,
        start_time=p.start_time,
        end_time=p.end_time,
        is_break=p.is_break,
    )


async def periods_of(db: AsyncSession, branch_id: int) -> list[PeriodOut]:
    rows = await db.scalars(
        select(PeriodSlot)
        .where(PeriodSlot.branch_id == branch_id)
        .order_by(PeriodSlot.sequence, PeriodSlot.id)
    )
    return [period_out(p) for p in rows.all()]


async def _commit_or_conflict(db: AsyncSession, detail: str, code: str) -> None:
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        raise conflict(detail, code) from None


# ---------------------------------------------------------------- periods


async def student_in_scope(db: AsyncSession, actor: User, student_id: int) -> Student:
    student: Student | None = await db.scalar(
        scope_students(select(Student), actor).where(Student.id == student_id)
    )
    if student is None:
        raise not_found("Student")
    return student


async def list_periods(
    db: AsyncSession, actor: User, branch_id: int | None, student_id: int | None
) -> list[PeriodOut]:
    if actor.role in FAMILY_ROLES:
        if student_id is None:
            raise common.unprocessable("student_id is required", "student_required")
        student = await student_in_scope(db, actor, student_id)
        return await periods_of(db, student.branch_id)
    branch = await resolve_branch(db, actor, branch_id)
    return await periods_of(db, branch.id)


async def _check_period(
    db: AsyncSession, branch_id: int, p: PeriodSlot, *, ignore_id: int | None
) -> None:
    if p.end_time <= p.start_time:
        raise common.unprocessable("The end time must be after the start time", "period_times")
    rows = await db.scalars(select(PeriodSlot).where(PeriodSlot.branch_id == branch_id))
    for other in rows.all():
        if other.id == ignore_id:
            continue
        if p.start_time < other.end_time and other.start_time < p.end_time:
            raise common.unprocessable(
                "This period overlaps another period of the branch", "period_overlap"
            )


async def create_period(
    db: AsyncSession, actor: User, branch_id: int | None, data: PeriodIn
) -> PeriodOut:
    _require_config(actor)
    branch = await resolve_branch(db, actor, branch_id)
    period = PeriodSlot(
        school_id=branch.school_id,
        branch_id=branch.id,
        name=data.name,
        sequence=data.sequence,
        start_time=data.start_time,
        end_time=data.end_time,
        is_break=data.is_break,
    )
    await _check_period(db, branch.id, period, ignore_id=None)
    db.add(period)
    await _commit_or_conflict(db, "A period with this number already exists", "period_exists")
    await audit.record(db, actor, "timetable.period.created", "period_slot", period.id)
    await db.commit()
    return period_out(period)


async def _get_period(db: AsyncSession, actor: User, period_id: int) -> PeriodSlot:
    period: PeriodSlot | None = await db.scalar(
        scope_exams(select(PeriodSlot), PeriodSlot, actor).where(PeriodSlot.id == period_id)
    )
    if period is None:
        raise not_found("Period")
    return period


async def _entry_count(db: AsyncSession, period_id: int) -> int:
    count: int | None = await db.scalar(
        select(func.count())
        .select_from(TimetableEntry)
        .where(TimetableEntry.period_id == period_id)
    )
    return count or 0


async def update_period(
    db: AsyncSession, actor: User, period_id: int, data: PeriodPatch
) -> PeriodOut:
    _require_config(actor)
    period = await _get_period(db, actor, period_id)
    if data.name is not None:
        period.name = data.name
    if data.sequence is not None:
        period.sequence = data.sequence
    if data.start_time is not None:
        period.start_time = data.start_time
    if data.end_time is not None:
        period.end_time = data.end_time
    if data.is_break is not None:
        if data.is_break and not period.is_break and await _entry_count(db, period.id):
            raise common.unprocessable(
                "Remove the lessons from this period before making it a break",
                "period_has_entries",
            )
        period.is_break = data.is_break
    await _check_period(db, period.branch_id, period, ignore_id=period.id)
    await _commit_or_conflict(db, "A period with this number already exists", "period_exists")
    await audit.record(
        db,
        actor,
        "timetable.period.updated",
        "period_slot",
        period.id,
        detail={"fields": sorted(data.model_fields_set)},
    )
    await db.commit()
    return period_out(period)


async def delete_period(db: AsyncSession, actor: User, period_id: int) -> None:
    _require_config(actor)
    period = await _get_period(db, actor, period_id)
    if await _entry_count(db, period.id):
        raise conflict("This period is used in a timetable", "period_in_use")
    await db.delete(period)
    await audit.record(db, actor, "timetable.period.deleted", "period_slot", period_id)
    await db.commit()


# ---------------------------------------------------------------- entries


def _entry_out(e: TimetableEntry, subject_name: str, teacher_name: str | None) -> EntryOut:
    return EntryOut(
        id=e.id,
        section_id=e.section_id,
        academic_year_id=e.academic_year_id,
        weekday=e.weekday,
        period_id=e.period_id,
        subject_id=e.subject_id,
        subject_name=subject_name,
        teacher_id=e.teacher_id,
        teacher_name=teacher_name,
        room=e.room,
    )


async def _section_entries(db: AsyncSession, section_id: int, year_id: int) -> list[EntryOut]:
    rows = await db.execute(
        select(TimetableEntry, Subject.name, User.full_name)
        .join(Subject, Subject.id == TimetableEntry.subject_id)
        .outerjoin(User, User.id == TimetableEntry.teacher_id)
        .where(
            TimetableEntry.section_id == section_id,
            TimetableEntry.academic_year_id == year_id,
        )
        .order_by(TimetableEntry.weekday, TimetableEntry.period_id)
    )
    return [_entry_out(e, sn, tn) for e, sn, tn in rows.all()]


def _section_ref(section: Section, cls: SchoolClass) -> SectionRef:
    return SectionRef(id=section.id, name=section.name, class_id=cls.id, class_name=cls.name)


async def section_week(
    db: AsyncSession, actor: User, section_id: int, year_id: int | None
) -> SectionWeekOut:
    section, cls = await common.get_section(db, actor, section_id)
    year = await common.resolve_year(db, section.school_id, year_id)
    return SectionWeekOut(
        section=_section_ref(section, cls),
        academic_year_id=year.id,
        periods=await periods_of(db, section.branch_id),
        entries=await _section_entries(db, section.id, year.id),
    )


async def put_entry(db: AsyncSession, actor: User, data: EntryPut) -> EntryOut:
    _require_config(actor)
    section, _ = await common.get_section(db, actor, data.section_id)
    branch_id = section.branch_id
    year = await common.resolve_year(db, section.school_id, data.academic_year_id)
    period: PeriodSlot | None = await db.scalar(
        scope_exams(select(PeriodSlot), PeriodSlot, actor).where(
            PeriodSlot.id == data.period_id, PeriodSlot.branch_id == branch_id
        )
    )
    if period is None:
        raise not_found("Period")
    if period.is_break:
        raise common.unprocessable("A break cannot hold a lesson", "break_period")
    subject = await common.get_subject(db, actor, data.subject_id, branch_id)
    teacher: User | None = None
    if data.teacher_id is not None:
        teacher = await common.get_teacher(db, actor, data.teacher_id, branch_id)
        clash = await db.scalar(
            select(TimetableEntry.id).where(
                TimetableEntry.teacher_id == teacher.id,
                TimetableEntry.academic_year_id == year.id,
                TimetableEntry.weekday == data.weekday,
                TimetableEntry.period_id == period.id,
                TimetableEntry.section_id != section.id,
            )
        )
        if clash is not None:
            raise conflict(
                "This teacher already teaches another section in this period", "teacher_clash"
            )
    entry: TimetableEntry | None = await db.scalar(
        select(TimetableEntry).where(
            TimetableEntry.section_id == section.id,
            TimetableEntry.academic_year_id == year.id,
            TimetableEntry.weekday == data.weekday,
            TimetableEntry.period_id == period.id,
        )
    )
    created = entry is None
    if entry is None:
        entry = TimetableEntry(
            school_id=section.school_id,
            branch_id=branch_id,
            academic_year_id=year.id,
            section_id=section.id,
            weekday=data.weekday,
            period_id=period.id,
            subject_id=subject.id,
        )
        db.add(entry)
    entry.subject_id = subject.id
    entry.teacher_id = teacher.id if teacher else None
    entry.room = data.room or None
    await _commit_or_conflict(db, "This lesson was changed by someone else", "entry_conflict")
    await audit.record(
        db,
        actor,
        "timetable.entry.created" if created else "timetable.entry.updated",
        "timetable_entry",
        entry.id,
    )
    await db.commit()
    return _entry_out(entry, subject.name, teacher.full_name if teacher else None)


async def delete_entry(db: AsyncSession, actor: User, entry_id: int) -> None:
    _require_config(actor)
    entry: TimetableEntry | None = await db.scalar(
        scope_exams(select(TimetableEntry), TimetableEntry, actor).where(
            TimetableEntry.id == entry_id
        )
    )
    if entry is None:
        raise not_found("Timetable entry")
    await db.delete(entry)
    await audit.record(db, actor, "timetable.entry.deleted", "timetable_entry", entry_id)
    await db.commit()


# ---------------------------------------------------------------- weeks of a person


async def _teacher_entries(
    db: AsyncSession, teacher: User, year_id: int, branch_id: int
) -> list[PersonEntryOut]:
    rows = await db.execute(
        select(TimetableEntry, Subject.name, Section.name, SchoolClass.id, SchoolClass.name)
        .join(Subject, Subject.id == TimetableEntry.subject_id)
        .join(Section, Section.id == TimetableEntry.section_id)
        .join(SchoolClass, SchoolClass.id == Section.class_id)
        .where(
            TimetableEntry.teacher_id == teacher.id,
            TimetableEntry.academic_year_id == year_id,
            TimetableEntry.branch_id == branch_id,
        )
        .order_by(TimetableEntry.weekday, TimetableEntry.period_id)
    )
    return [
        PersonEntryOut(
            id=e.id,
            weekday=e.weekday,
            period_id=e.period_id,
            subject_id=e.subject_id,
            subject_name=sn,
            section_id=e.section_id,
            section_name=sec,
            class_id=cid,
            class_name=cn,
            room=e.room,
        )
        for e, sn, sec, cid, cn in rows.all()
    ]


async def teacher_week(
    db: AsyncSession, actor: User, teacher_id: int, year_id: int | None
) -> TeacherWeekOut:
    teacher: User | None
    if actor.role == Role.TEACHER:
        if teacher_id != actor.id:
            raise common.forbidden()
        teacher = actor
    else:
        common.require_role(actor, CONFIG_ROLES)
        teacher = await db.scalar(
            scope_users(select(User), actor).where(User.id == teacher_id, User.role == Role.TEACHER)
        )
    if teacher is None or teacher.school_id is None or teacher.branch_id is None:
        raise not_found("Teacher")
    year = await common.resolve_year(db, teacher.school_id, year_id)
    return TeacherWeekOut(
        teacher=TeacherRef(id=teacher.id, full_name=teacher.full_name),
        academic_year_id=year.id,
        periods=await periods_of(db, teacher.branch_id),
        entries=await _teacher_entries(db, teacher, year.id, teacher.branch_id),
    )


async def student_week(
    db: AsyncSession, actor: User, student_id: int, year_id: int | None
) -> StudentWeekOut:
    student = await student_in_scope(db, actor, student_id)
    year = await common.resolve_year(db, student.school_id, year_id)
    row = (
        await db.execute(
            select(Section, SchoolClass)
            .join(Enrollment, Enrollment.section_id == Section.id)
            .join(SchoolClass, SchoolClass.id == Section.class_id)
            .where(
                Enrollment.student_id == student.id,
                Enrollment.academic_year_id == year.id,
            )
        )
    ).first()
    return StudentWeekOut(
        student=StudentRef(
            id=student.id, full_name=f"{student.first_name} {student.last_name}".strip()
        ),
        academic_year_id=year.id,
        section=_section_ref(row[0], row[1]) if row else None,
        periods=await periods_of(db, student.branch_id),
        entries=await _section_entries(db, row[0].id, year.id) if row else [],
    )
