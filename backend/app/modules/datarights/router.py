import json
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status

from app.core.deps import CurrentUser, DbSession
from app.modules.datarights import export, service
from app.modules.datarights.models import RequestStatus
from app.modules.datarights.schemas import (
    DataRequestCreate,
    DataRequestOut,
    DataRequestPage,
    DataRequestUpdate,
)
from app.modules.settings.deps import require_feature

router = APIRouter(tags=["data-rights"])
student_router = APIRouter(
    tags=["data-rights"], dependencies=[Depends(require_feature("students"))]
)


def _download(data: object, filename: str) -> Response:
    return Response(
        content=json.dumps(data, indent=2, ensure_ascii=False),
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/data-requests", response_model=DataRequestOut, status_code=status.HTTP_201_CREATED)
async def create_request(
    data: DataRequestCreate, db: DbSession, actor: CurrentUser
) -> DataRequestOut:
    return await service.create_request(db, actor, data)


@router.get("/data-requests/mine", response_model=DataRequestPage)
async def my_requests(
    db: DbSession,
    actor: CurrentUser,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 25,
) -> DataRequestPage:
    return await service.list_mine(db, actor, page, page_size)


@router.get("/data-requests", response_model=DataRequestPage)
async def list_requests(
    db: DbSession,
    actor: CurrentUser,
    request_status: Annotated[RequestStatus | None, Query(alias="status")] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 25,
) -> DataRequestPage:
    return await service.list_requests(db, actor, request_status, page, page_size)


@router.patch("/data-requests/{request_id}", response_model=DataRequestOut)
async def update_request(
    request_id: int, data: DataRequestUpdate, db: DbSession, actor: CurrentUser
) -> DataRequestOut:
    return await service.update_request(db, actor, request_id, data)


@router.get("/me/export")
async def export_me(db: DbSession, user: CurrentUser) -> Response:
    return _download(await export.me_export(db, user), "my-data.json")


@student_router.get("/students/{student_id}/export")
async def export_student(student_id: int, db: DbSession, actor: CurrentUser) -> Response:
    return _download(
        await export.student_export(db, actor, student_id), f"student-{student_id}-data.json"
    )
