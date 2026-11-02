from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status

from app.core.deps import CurrentUser, DbSession
from app.modules.notices import service
from app.modules.notices.models import NoticeCategory
from app.modules.notices.schemas import (
    NoticeCreate,
    NoticeOut,
    NoticePage,
    NoticeUpdate,
    UnreadCount,
)
from app.modules.settings.deps import require_feature

router = APIRouter(
    prefix="/notices", tags=["notices"], dependencies=[Depends(require_feature("notices"))]
)


@router.get("", response_model=NoticePage)
async def list_notices(
    db: DbSession,
    actor: CurrentUser,
    category: NoticeCategory | None = None,
    q: Annotated[str | None, Query(max_length=100)] = None,
    unread_only: bool = False,
    pinned: bool | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=50)] = 20,
) -> NoticePage:
    return await service.list_notices(
        db,
        actor,
        category=category,
        q=q,
        unread_only=unread_only,
        pinned=pinned,
        page=page,
        page_size=page_size,
    )


@router.post("", response_model=NoticeOut, status_code=status.HTTP_201_CREATED)
async def create_notice(data: NoticeCreate, db: DbSession, actor: CurrentUser) -> NoticeOut:
    return await service.create_notice(db, actor, data)


# Fixed paths must be declared before the `/{notice_id}` routes.
@router.get("/unread-count", response_model=UnreadCount)
async def unread_count(db: DbSession, actor: CurrentUser) -> UnreadCount:
    return UnreadCount(count=await service.unread_count(db, actor))


@router.post("/read-all", status_code=status.HTTP_204_NO_CONTENT)
async def read_all(db: DbSession, actor: CurrentUser) -> Response:
    await service.mark_all_read(db, actor)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{notice_id}", response_model=NoticeOut)
async def get_notice(notice_id: int, db: DbSession, actor: CurrentUser) -> NoticeOut:
    return await service.get_notice(db, actor, notice_id)


@router.patch("/{notice_id}", response_model=NoticeOut)
async def update_notice(
    notice_id: int, data: NoticeUpdate, db: DbSession, actor: CurrentUser
) -> NoticeOut:
    return await service.update_notice(db, actor, notice_id, data)


@router.delete("/{notice_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_notice(notice_id: int, db: DbSession, actor: CurrentUser) -> Response:
    await service.delete_notice(db, actor, notice_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{notice_id}/read", status_code=status.HTTP_204_NO_CONTENT)
async def mark_read(notice_id: int, db: DbSession, actor: CurrentUser) -> Response:
    await service.mark_read(db, actor, notice_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
