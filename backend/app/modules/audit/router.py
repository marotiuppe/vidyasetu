from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response

from app.core.deps import CurrentUser, DbSession
from app.modules.audit import service
from app.modules.audit.schemas import AuditPage

router = APIRouter(prefix="/audit", tags=["audit"])


class _Filters:
    def __init__(
        self,
        date_from: Annotated[date | None, Query(alias="from")] = None,
        date_to: Annotated[date | None, Query(alias="to")] = None,
        action: Annotated[str | None, Query(max_length=50)] = None,
        actor_id: int | None = None,
        entity_type: Annotated[str | None, Query(max_length=30)] = None,
        school_id: int | None = None,
    ) -> None:
        self.filters = service.AuditFilters(
            date_from, date_to, action, actor_id, entity_type, school_id
        )


Filters = Annotated[_Filters, Depends()]


@router.get("", response_model=AuditPage)
async def list_audit(
    db: DbSession,
    actor: CurrentUser,
    f: Filters,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=200)] = 50,
) -> AuditPage:
    return await service.list_entries(db, actor, f.filters, page, page_size)


@router.get("/export.csv")
async def export_audit(db: DbSession, actor: CurrentUser, f: Filters) -> Response:
    content = await service.export_csv(db, actor, f.filters)
    return Response(
        content=content,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="audit-log.csv"'},
    )
