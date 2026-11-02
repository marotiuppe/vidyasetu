from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.tenant import scope_branches, scope_tenant
from app.modules.academics.models import AcademicYear, SchoolClass, Section
from app.modules.academics.schemas import (
    AcademicYearCreate,
    AcademicYearUpdate,
    ClassCreate,
    ClassUpdate,
    SectionCreate,
    SectionUpdate,
)
from app.modules.branches.models import Branch
from app.modules.schools.models import School
from app.modules.users.models import Role, User


def _not_found(what: str) -> HTTPException:
    return HTTPException(status.HTTP_404_NOT_FOUND, detail=f"{what} not found")


async def _commit(db: AsyncSession, conflict: str) -> None:
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, detail=conflict) from None


async def _get_scoped(db: AsyncSession, actor: User, model: Any, item_id: int, what: str) -> Any:
    item = await db.scalar(scope_tenant(select(model), model, actor).where(model.id == item_id))
    if item is None:
        raise _not_found(what)
    return item


# ---- academic years (school-wide) ----


async def list_years(db: AsyncSession, actor: User) -> list[AcademicYear]:
    stmt = scope_tenant(select(AcademicYear), AcademicYear, actor)
    return list(await db.scalars(stmt.order_by(AcademicYear.start_date.desc())))


async def _clear_current(db: AsyncSession, school_id: int, except_id: int | None) -> None:
    stmt = update(AcademicYear).where(AcademicYear.school_id == school_id)
    if except_id is not None:
        stmt = stmt.where(AcademicYear.id != except_id)
    await db.execute(stmt.values(is_current=False))


async def create_year(db: AsyncSession, actor: User, data: AcademicYearCreate) -> AcademicYear:
    school_id = data.school_id if actor.role == Role.SUPER_ADMIN else actor.school_id
    if school_id is None or await db.get(School, school_id) is None:
        raise _not_found("School")
    year = AcademicYear(
        school_id=school_id,
        name=data.name,
        start_date=data.start_date,
        end_date=data.end_date,
        is_current=data.is_current,
    )
    db.add(year)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT, detail="Academic year name already used"
        ) from None
    if data.is_current:
        await _clear_current(db, school_id, year.id)
    await _commit(db, "Academic year name already used")
    return year


async def update_year(
    db: AsyncSession, actor: User, year_id: int, data: AcademicYearUpdate
) -> AcademicYear:
    year: AcademicYear = await _get_scoped(db, actor, AcademicYear, year_id, "Academic year")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(year, field, value)
    if year.end_date <= year.start_date:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, detail="end_date must be after start_date"
        )
    if year.is_current:
        await _clear_current(db, year.school_id, year.id)
    await _commit(db, "Academic year name already used")
    return year


# ---- classes (per branch) ----


async def list_classes(db: AsyncSession, actor: User, branch_id: int | None) -> list[SchoolClass]:
    stmt = scope_tenant(select(SchoolClass), SchoolClass, actor)
    if branch_id is not None:
        stmt = stmt.where(SchoolClass.branch_id == branch_id)
    return list(await db.scalars(stmt.order_by(SchoolClass.branch_id, SchoolClass.level)))


async def create_class(db: AsyncSession, actor: User, data: ClassCreate) -> SchoolClass:
    branch_id = actor.branch_id if actor.branch_id is not None else data.branch_id
    if branch_id is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail="branch_id required")
    branch = await db.scalar(scope_branches(select(Branch), actor).where(Branch.id == branch_id))
    if branch is None:
        raise _not_found("Branch")
    school_class = SchoolClass(
        school_id=branch.school_id, branch_id=branch.id, name=data.name, level=data.level
    )
    db.add(school_class)
    await _commit(db, "A class with this level already exists in the branch")
    return school_class


async def update_class(
    db: AsyncSession, actor: User, class_id: int, data: ClassUpdate
) -> SchoolClass:
    school_class: SchoolClass = await _get_scoped(db, actor, SchoolClass, class_id, "Class")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(school_class, field, value)
    await _commit(db, "A class with this level already exists in the branch")
    return school_class


# ---- sections (per class) ----


async def list_sections(db: AsyncSession, actor: User, class_id: int | None) -> list[Section]:
    stmt = scope_tenant(select(Section), Section, actor)
    if class_id is not None:
        stmt = stmt.where(Section.class_id == class_id)
    return list(await db.scalars(stmt.order_by(Section.class_id, Section.name)))


async def create_section(db: AsyncSession, actor: User, data: SectionCreate) -> Section:
    school_class: SchoolClass = await _get_scoped(db, actor, SchoolClass, data.class_id, "Class")
    section = Section(
        school_id=school_class.school_id,
        branch_id=school_class.branch_id,
        class_id=school_class.id,
        name=data.name,
    )
    db.add(section)
    await _commit(db, "Section already exists in this class")
    return section


async def update_section(
    db: AsyncSession, actor: User, section_id: int, data: SectionUpdate
) -> Section:
    section: Section = await _get_scoped(db, actor, Section, section_id, "Section")
    section.name = data.name
    await _commit(db, "Section already exists in this class")
    return section
