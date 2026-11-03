from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, status

from app.core.deps import CurrentUser, DbSession, require_roles
from app.modules.promotion import service
from app.modules.promotion.schemas import (
    ApplyRequest,
    BatchDetail,
    BatchOut,
    PreviewOut,
    PreviewRequest,
)
from app.modules.settings.deps import require_feature
from app.modules.users.models import Role

# School staff who run the year-end. Parents, students, teachers, clerks and accountants never
# reach promotion. Branch-level staff are limited to their own branch (service).
_staff = require_roles(Role.SCHOOL_OWNER, Role.MANAGEMENT, Role.HEADMASTER)

router = APIRouter(
    prefix="/promotion",
    tags=["promotion"],
    dependencies=[Depends(require_feature("students")), Depends(_staff)],
)


@router.post("/preview", response_model=PreviewOut)
async def preview(data: PreviewRequest, db: DbSession, actor: CurrentUser) -> PreviewOut:
    return await service.preview(db, actor, data)


@router.post("/apply", response_model=BatchOut, status_code=status.HTTP_201_CREATED)
async def apply(data: ApplyRequest, db: DbSession, actor: CurrentUser) -> BatchOut:
    return await service.apply(db, actor, data)


@router.get("/batches", response_model=list[BatchOut])
async def list_batches(
    db: DbSession,
    actor: CurrentUser,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 25,
) -> list[BatchOut]:
    return await service.list_batches(db, actor, page, page_size)


@router.get("/batches/{batch_id}", response_model=BatchDetail)
async def get_batch(
    batch_id: Annotated[int, Path(ge=1)], db: DbSession, actor: CurrentUser
) -> BatchDetail:
    return await service.get_batch(db, actor, batch_id)


@router.post("/batches/{batch_id}/undo", response_model=BatchOut)
async def undo(batch_id: Annotated[int, Path(ge=1)], db: DbSession, actor: CurrentUser) -> BatchOut:
    return await service.undo(db, actor, batch_id)
