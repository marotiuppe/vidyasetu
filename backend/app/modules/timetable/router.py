"""Timetable endpoints: period slots, section weeks, entries, and the weeks of teachers and
students. Writes need a configuring role; see service.py for the read rules."""

from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, Response, status

from app.core.deps import CurrentUser, DbSession, require_roles
from app.modules.settings.deps import require_feature
from app.modules.timetable import service
from app.modules.timetable.common import CONFIG_ROLES, FAMILY_ROLES, RESULT_STAFF_ROLES
from app.modules.timetable.schemas import (
    EntryOut,
    EntryPut,
    PeriodIn,
    PeriodOut,
    PeriodPatch,
    SectionWeekOut,
    StudentWeekOut,
    TeacherWeekOut,
)
from app.modules.users.models import Role

router = APIRouter(
    prefix="/timetable",
    tags=["timetable"],
    dependencies=[Depends(require_feature("timetable"))],
)

_configure = Depends(require_roles(*CONFIG_ROLES))
_staff = Depends(require_roles(*RESULT_STAFF_ROLES))
_readers = Depends(require_roles(*RESULT_STAFF_ROLES, *FAMILY_ROLES))
_teacher_or_config = Depends(require_roles(*CONFIG_ROLES, Role.TEACHER))

IdQuery = Annotated[int | None, Query(ge=1)]
Id = Annotated[int, Path(ge=1)]


@router.get("/periods", response_model=list[PeriodOut], dependencies=[_readers])
async def list_periods(
    db: DbSession,
    actor: CurrentUser,
    branch_id: IdQuery = None,
    student_id: IdQuery = None,
) -> list[PeriodOut]:
    return await service.list_periods(db, actor, branch_id, student_id)


@router.post(
    "/periods",
    response_model=PeriodOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[_configure],
)
async def create_period(
    data: PeriodIn, db: DbSession, actor: CurrentUser, branch_id: IdQuery = None
) -> PeriodOut:
    return await service.create_period(db, actor, branch_id, data)


@router.patch("/periods/{period_id}", response_model=PeriodOut, dependencies=[_configure])
async def update_period(
    period_id: Id, data: PeriodPatch, db: DbSession, actor: CurrentUser
) -> PeriodOut:
    return await service.update_period(db, actor, period_id, data)


@router.delete(
    "/periods/{period_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[_configure]
)
async def delete_period(period_id: Id, db: DbSession, actor: CurrentUser) -> Response:
    await service.delete_period(db, actor, period_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/sections/{section_id}", response_model=SectionWeekOut, dependencies=[_staff])
async def section_week(
    section_id: Id, db: DbSession, actor: CurrentUser, academic_year_id: IdQuery = None
) -> SectionWeekOut:
    return await service.section_week(db, actor, section_id, academic_year_id)


@router.put("/entries", response_model=EntryOut, dependencies=[_configure])
async def put_entry(data: EntryPut, db: DbSession, actor: CurrentUser) -> EntryOut:
    return await service.put_entry(db, actor, data)


@router.delete(
    "/entries/{entry_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[_configure]
)
async def delete_entry(entry_id: Id, db: DbSession, actor: CurrentUser) -> Response:
    await service.delete_entry(db, actor, entry_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/me",
    response_model=TeacherWeekOut,
    dependencies=[Depends(require_roles(Role.TEACHER))],
)
async def my_week(
    db: DbSession, actor: CurrentUser, academic_year_id: IdQuery = None
) -> TeacherWeekOut:
    return await service.teacher_week(db, actor, actor.id, academic_year_id)


@router.get(
    "/teachers/{teacher_id}", response_model=TeacherWeekOut, dependencies=[_teacher_or_config]
)
async def teacher_week(
    teacher_id: Id, db: DbSession, actor: CurrentUser, academic_year_id: IdQuery = None
) -> TeacherWeekOut:
    return await service.teacher_week(db, actor, teacher_id, academic_year_id)


@router.get("/students/{student_id}", response_model=StudentWeekOut, dependencies=[_readers])
async def student_week(
    student_id: Id, db: DbSession, actor: CurrentUser, academic_year_id: IdQuery = None
) -> StudentWeekOut:
    return await service.student_week(db, actor, student_id, academic_year_id)
