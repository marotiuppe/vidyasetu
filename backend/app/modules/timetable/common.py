"""Shared helpers for the timetable and homework services: role sets, year, subject and teacher
lookups. Every lookup goes through the tenant scope helpers."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.tenant import scope_exams
from app.modules.academics.models import AcademicYear, SchoolClass, Section
from app.modules.exams.common import (
    CONFIG_ROLES,
    FAMILY_ROLES,
    RESULT_STAFF_ROLES,
    conflict,
    forbidden,
    not_found,
    require_role,
    unprocessable,
)
from app.modules.exams.models import Subject
from app.modules.users.models import Role, User

__all__ = [
    "CONFIG_ROLES",
    "FAMILY_ROLES",
    "RESULT_STAFF_ROLES",
    "conflict",
    "forbidden",
    "get_section",
    "get_subject",
    "get_teacher",
    "not_found",
    "require_role",
    "resolve_year",
    "unprocessable",
]


async def resolve_year(db: AsyncSession, school_id: int, year_id: int | None) -> AcademicYear:
    """The named academic year of the school, or its current one when none is named."""
    stmt = select(AcademicYear).where(AcademicYear.school_id == school_id)
    if year_id is not None:
        stmt = stmt.where(AcademicYear.id == year_id)
    else:
        stmt = stmt.where(AcademicYear.is_current.is_(True))
    year: AcademicYear | None = await db.scalar(stmt.limit(1))
    if year is None:
        if year_id is None:
            raise unprocessable("No current academic year is set", "no_current_year")
        raise not_found("Academic year")
    return year


async def get_section(
    db: AsyncSession, actor: User, section_id: int
) -> tuple[Section, SchoolClass]:
    """A section of the actor's reach (own branch; the owner's whole school)."""
    row = (
        await db.execute(
            scope_exams(select(Section, SchoolClass), Section, actor)
            .join(SchoolClass, SchoolClass.id == Section.class_id)
            .where(Section.id == section_id)
        )
    ).first()
    if row is None:
        raise not_found("Section")
    return row[0], row[1]


async def get_subject(db: AsyncSession, actor: User, subject_id: int, branch_id: int) -> Subject:
    subject: Subject | None = await db.scalar(
        scope_exams(select(Subject), Subject, actor).where(
            Subject.id == subject_id, Subject.branch_id == branch_id
        )
    )
    if subject is None:
        raise not_found("Subject")
    if not subject.active:
        raise unprocessable("This subject is switched off", "subject_inactive")
    return subject


async def get_teacher(db: AsyncSession, actor: User, teacher_id: int, branch_id: int) -> User:
    """An active teacher of the given branch (never from another branch or school)."""
    teacher: User | None = await db.scalar(
        select(User).where(
            User.id == teacher_id,
            User.school_id == actor.school_id,
            User.branch_id == branch_id,
            User.role == Role.TEACHER,
            User.is_active.is_(True),
        )
    )
    if teacher is None:
        raise not_found("Teacher")
    return teacher
