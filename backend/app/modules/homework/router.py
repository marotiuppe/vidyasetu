"""Homework endpoints. Staff read their branch (the school owner may name a branch); parents and
students read through `student_id`. Config roles write any homework, a teacher only their own."""

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, Response, status

from app.core.deps import CurrentUser, DbSession, require_roles
from app.modules.homework import service
from app.modules.homework.schemas import HomeworkIn, HomeworkOut, HomeworkPage, HomeworkPatch
from app.modules.settings.deps import require_feature
from app.modules.timetable.common import FAMILY_ROLES, RESULT_STAFF_ROLES

router = APIRouter(
    prefix="/homework",
    tags=["homework"],
    dependencies=[Depends(require_feature("homework"))],
)

_readers = Depends(require_roles(*RESULT_STAFF_ROLES, *FAMILY_ROLES))
_writers = Depends(require_roles(*service.WRITE_ROLES))

IdQuery = Annotated[int | None, Query(ge=1)]
Id = Annotated[int, Path(ge=1)]


@router.get("", response_model=HomeworkPage, dependencies=[_readers])
async def list_homework(
    db: DbSession,
    actor: CurrentUser,
    section_id: IdQuery = None,
    subject_id: IdQuery = None,
    from_date: Annotated[date | None, Query(alias="from")] = None,
    to_date: Annotated[date | None, Query(alias="to")] = None,
    student_id: IdQuery = None,
    branch_id: IdQuery = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 25,
) -> HomeworkPage:
    return await service.list_homework(
        db,
        actor,
        section_id=section_id,
        subject_id=subject_id,
        from_date=from_date,
        to_date=to_date,
        student_id=student_id,
        branch_id=branch_id,
        page=page,
        page_size=page_size,
    )


@router.post(
    "", response_model=HomeworkOut, status_code=status.HTTP_201_CREATED, dependencies=[_writers]
)
async def create_homework(data: HomeworkIn, db: DbSession, actor: CurrentUser) -> HomeworkOut:
    return await service.create_homework(db, actor, data)


@router.patch("/{homework_id}", response_model=HomeworkOut, dependencies=[_writers])
async def update_homework(
    homework_id: Id, data: HomeworkPatch, db: DbSession, actor: CurrentUser
) -> HomeworkOut:
    return await service.update_homework(db, actor, homework_id, data)


@router.delete("/{homework_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[_writers])
async def delete_homework(homework_id: Id, db: DbSession, actor: CurrentUser) -> Response:
    await service.delete_homework(db, actor, homework_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
