from fastapi import APIRouter, Depends, status

from app.core.deps import CurrentUser, DbSession, require_roles
from app.modules.academics import service
from app.modules.academics.schemas import (
    AcademicYearCreate,
    AcademicYearOut,
    AcademicYearUpdate,
    ClassCreate,
    ClassOut,
    ClassUpdate,
    SectionCreate,
    SectionOut,
    SectionUpdate,
)
from app.modules.users.models import Role

router = APIRouter(tags=["academics"])

_year_admins = require_roles(Role.SUPER_ADMIN, Role.SCHOOL_OWNER)
_class_admins = require_roles(
    Role.SUPER_ADMIN, Role.SCHOOL_OWNER, Role.MANAGEMENT, Role.HEADMASTER
)


@router.get("/academic-years", response_model=list[AcademicYearOut])
async def list_years(db: DbSession, actor: CurrentUser) -> list[AcademicYearOut]:
    return [AcademicYearOut.model_validate(y) for y in await service.list_years(db, actor)]


@router.post(
    "/academic-years",
    response_model=AcademicYearOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(_year_admins)],
)
async def create_year(
    data: AcademicYearCreate, db: DbSession, actor: CurrentUser
) -> AcademicYearOut:
    return AcademicYearOut.model_validate(await service.create_year(db, actor, data))


@router.patch(
    "/academic-years/{year_id}",
    response_model=AcademicYearOut,
    dependencies=[Depends(_year_admins)],
)
async def update_year(
    year_id: int, data: AcademicYearUpdate, db: DbSession, actor: CurrentUser
) -> AcademicYearOut:
    return AcademicYearOut.model_validate(await service.update_year(db, actor, year_id, data))


@router.get("/classes", response_model=list[ClassOut])
async def list_classes(
    db: DbSession, actor: CurrentUser, branch_id: int | None = None
) -> list[ClassOut]:
    return [ClassOut.model_validate(c) for c in await service.list_classes(db, actor, branch_id)]


@router.post(
    "/classes",
    response_model=ClassOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(_class_admins)],
)
async def create_class(data: ClassCreate, db: DbSession, actor: CurrentUser) -> ClassOut:
    return ClassOut.model_validate(await service.create_class(db, actor, data))


@router.patch(
    "/classes/{class_id}", response_model=ClassOut, dependencies=[Depends(_class_admins)]
)
async def update_class(
    class_id: int, data: ClassUpdate, db: DbSession, actor: CurrentUser
) -> ClassOut:
    return ClassOut.model_validate(await service.update_class(db, actor, class_id, data))


@router.get("/sections", response_model=list[SectionOut])
async def list_sections(
    db: DbSession, actor: CurrentUser, class_id: int | None = None
) -> list[SectionOut]:
    return [SectionOut.model_validate(s) for s in await service.list_sections(db, actor, class_id)]


@router.post(
    "/sections",
    response_model=SectionOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(_class_admins)],
)
async def create_section(data: SectionCreate, db: DbSession, actor: CurrentUser) -> SectionOut:
    return SectionOut.model_validate(await service.create_section(db, actor, data))


@router.patch(
    "/sections/{section_id}", response_model=SectionOut, dependencies=[Depends(_class_admins)]
)
async def update_section(
    section_id: int, data: SectionUpdate, db: DbSession, actor: CurrentUser
) -> SectionOut:
    return SectionOut.model_validate(await service.update_section(db, actor, section_id, data))
