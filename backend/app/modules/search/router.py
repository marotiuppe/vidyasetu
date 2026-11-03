from typing import Annotated

from fastapi import APIRouter, Query

from app.core.deps import CurrentUser, DbSession
from app.modules.search import service
from app.modules.search.schemas import SearchResponse

router = APIRouter(tags=["search"])


@router.get("/search", response_model=SearchResponse)
async def search(
    db: DbSession,
    actor: CurrentUser,
    q: Annotated[str, Query(min_length=2, max_length=60)],
    limit: Annotated[int, Query(ge=1, le=10)] = 5,
) -> SearchResponse:
    return await service.search(db, actor, q, limit)
