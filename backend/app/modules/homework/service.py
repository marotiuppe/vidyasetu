"""Homework: staff of a branch write and read it; parents and students read the homework of their
own child's section only (through the student scope). A teacher changes only their own homework.
Writes are audited with ids only (never the text)."""

from datetime import date, datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.tenant import scope_exams, scope_students
from app.modules.academics.models import AcademicYear, SchoolClass, Section
from app.modules.audit import service as audit
from app.modules.exams.common import branch_filter
from app.modules.exams.models import Subject
from app.modules.homework.models import Homework
from app.modules.homework.schemas import HomeworkIn, HomeworkOut, HomeworkPage, HomeworkPatch
from app.modules.students.models import Enrollment, Student
from app.modules.timetable import common
from app.modules.timetable.common import FAMILY_ROLES, not_found
from app.modules.users.models import Role, User

IST = timezone(timedelta(hours=5, minutes=30))
WRITE_ROLES = common.CONFIG_ROLES | {Role.TEACHER}


def today() -> date:
    return datetime.now(IST).date()


def _row_out(
    h: Homework, section_name: str, class_id: int, class_name: str, subject_name: str, teacher: str
) -> HomeworkOut:
    return HomeworkOut(
        id=h.id,
        branch_id=h.branch_id,
        academic_year_id=h.academic_year_id,
        section_id=h.section_id,
        section_name=section_name,
        class_id=class_id,
        class_name=class_name,
        subject_id=h.subject_id,
        subject_name=subject_name,
        teacher_id=h.teacher_id,
        teacher_name=teacher,
        title=h.title,
        description=h.description,
        assigned_on=h.assigned_on,
        due_date=h.due_date,
    )


async def _load_out(db: AsyncSession, homework_id: int) -> HomeworkOut:
    row = (
        await db.execute(
            select(
                Homework,
                Section.name,
                SchoolClass.id,
                SchoolClass.name,
                Subject.name,
                User.full_name,
            )
            .join(Section, Section.id == Homework.section_id)
            .join(SchoolClass, SchoolClass.id == Section.class_id)
            .join(Subject, Subject.id == Homework.subject_id)
            .join(User, User.id == Homework.teacher_id)
            .where(Homework.id == homework_id)
        )
    ).first()
    if row is None:
        raise not_found("Homework")
    return _row_out(*row)


async def list_homework(
    db: AsyncSession,
    actor: User,
    *,
    section_id: int | None,
    subject_id: int | None,
    from_date: date | None,
    to_date: date | None,
    student_id: int | None,
    branch_id: int | None,
    page: int,
    page_size: int,
) -> HomeworkPage:
    family = actor.role in FAMILY_ROLES
    if family and student_id is None:
        raise common.unprocessable("student_id is required", "student_required")
    stmt = (
        select(
            Homework, Section.name, SchoolClass.id, SchoolClass.name, Subject.name, User.full_name
        )
        .join(Section, Section.id == Homework.section_id)
        .join(SchoolClass, SchoolClass.id == Section.class_id)
        .join(Subject, Subject.id == Homework.subject_id)
        .join(User, User.id == Homework.teacher_id)
    )
    if family:
        stmt = stmt.where(Homework.school_id == actor.school_id)
    else:
        stmt = scope_exams(stmt, Homework, actor)
        wanted = await branch_filter(db, actor, branch_id)
        if wanted is not None:
            stmt = stmt.where(Homework.branch_id == wanted)
    if student_id is not None:
        student: Student | None = await db.scalar(
            scope_students(select(Student), actor).where(Student.id == student_id)
        )
        if student is None:
            raise not_found("Student")
        placement = (
            await db.execute(
                select(Enrollment.section_id, Enrollment.academic_year_id)
                .join(AcademicYear, AcademicYear.id == Enrollment.academic_year_id)
                .where(
                    Enrollment.student_id == student.id,
                    AcademicYear.school_id == student.school_id,
                    AcademicYear.is_current.is_(True),
                )
            )
        ).first()
        if placement is None or placement[0] is None:
            return HomeworkPage(items=[], total=0, page=page, page_size=page_size)
        stmt = stmt.where(
            Homework.section_id == placement[0],
            Homework.academic_year_id == placement[1],
            Homework.branch_id == student.branch_id,
        )
    if section_id is not None:
        stmt = stmt.where(Homework.section_id == section_id)
    if subject_id is not None:
        stmt = stmt.where(Homework.subject_id == subject_id)
    if from_date is not None:
        stmt = stmt.where(Homework.due_date >= from_date)
    if to_date is not None:
        stmt = stmt.where(Homework.due_date <= to_date)
    total: int = (
        await db.scalar(
            select(func.count()).select_from(stmt.with_only_columns(Homework.id).subquery())
        )
    ) or 0
    rows = await db.execute(
        stmt.order_by(Homework.due_date.desc(), Homework.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return HomeworkPage(
        items=[_row_out(*r) for r in rows.all()], total=total, page=page, page_size=page_size
    )


def _require_write(actor: User) -> None:
    common.require_role(actor, WRITE_ROLES)


def _check_dates(assigned_on: date, due_date: date) -> None:
    if due_date < assigned_on:
        raise common.unprocessable(
            "The due date cannot be before the assigned date", "homework_dates"
        )


async def create_homework(db: AsyncSession, actor: User, data: HomeworkIn) -> HomeworkOut:
    _require_write(actor)
    section, _ = await common.get_section(db, actor, data.section_id)
    year = await common.resolve_year(db, section.school_id, data.academic_year_id)
    subject = await common.get_subject(db, actor, data.subject_id, section.branch_id)
    assigned_on = data.assigned_on or today()
    _check_dates(assigned_on, data.due_date)
    homework = Homework(
        school_id=section.school_id,
        branch_id=section.branch_id,
        academic_year_id=year.id,
        section_id=section.id,
        subject_id=subject.id,
        teacher_id=actor.id,
        title=data.title,
        description=data.description or None,
        assigned_on=assigned_on,
        due_date=data.due_date,
    )
    db.add(homework)
    await db.flush()
    await audit.record(db, actor, "homework.created", "homework", homework.id)
    await db.commit()
    return await _load_out(db, homework.id)


async def _get_own(db: AsyncSession, actor: User, homework_id: int) -> Homework:
    homework: Homework | None = await db.scalar(
        scope_exams(select(Homework), Homework, actor).where(Homework.id == homework_id)
    )
    if homework is None:
        raise not_found("Homework")
    if actor.role == Role.TEACHER and homework.teacher_id != actor.id:
        raise common.forbidden()
    return homework


async def update_homework(
    db: AsyncSession, actor: User, homework_id: int, data: HomeworkPatch
) -> HomeworkOut:
    _require_write(actor)
    homework = await _get_own(db, actor, homework_id)
    if data.section_id is not None and data.section_id != homework.section_id:
        section, _ = await common.get_section(db, actor, data.section_id)
        if section.branch_id != homework.branch_id:
            raise not_found("Section")
        homework.section_id = section.id
    if data.subject_id is not None and data.subject_id != homework.subject_id:
        subject = await common.get_subject(db, actor, data.subject_id, homework.branch_id)
        homework.subject_id = subject.id
    if data.title is not None:
        homework.title = data.title
    if "description" in data.model_fields_set:
        homework.description = data.description or None
    if data.assigned_on is not None:
        homework.assigned_on = data.assigned_on
    if data.due_date is not None:
        homework.due_date = data.due_date
    _check_dates(homework.assigned_on, homework.due_date)
    await audit.record(
        db,
        actor,
        "homework.updated",
        "homework",
        homework.id,
        detail={"fields": sorted(data.model_fields_set)},
    )
    await db.commit()
    return await _load_out(db, homework.id)


async def delete_homework(db: AsyncSession, actor: User, homework_id: int) -> None:
    _require_write(actor)
    homework = await _get_own(db, actor, homework_id)
    await db.delete(homework)
    await audit.record(db, actor, "homework.deleted", "homework", homework_id)
    await db.commit()
