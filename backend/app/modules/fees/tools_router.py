"""Fee tools: concessions, late fees and reminders. Same feature switch and roles as fees."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status

from app.core.deps import CurrentUser, DbSession
from app.modules.fees import concessions, late_fees, reminders
from app.modules.fees.router import _managers, _readers
from app.modules.fees.tools_schemas import (
    ConcessionCreate,
    ConcessionOut,
    ConcessionPage,
    ConcessionUpdate,
    LateFeeApply,
    LateFeePreview,
    LateFeeResult,
    ReminderMark,
    ReminderMarked,
    ReminderPage,
)
from app.modules.settings.deps import require_feature

router = APIRouter(tags=["fees"], dependencies=[Depends(require_feature("fees"))])

Page = Annotated[int, Query(ge=1)]
PageSize = Annotated[int, Query(ge=1, le=100)]
Balance = Annotated[int, Query(ge=0, le=1_000_000_000_00)]
DaysAhead = Annotated[int | None, Query(ge=0, le=365)]


# ---- concessions ----


@router.get("/fees/concessions", response_model=ConcessionPage, dependencies=[_readers])
async def list_concessions(
    db: DbSession,
    actor: CurrentUser,
    student_id: int | None = None,
    academic_year_id: int | None = None,
    page: Page = 1,
    page_size: PageSize = 25,
) -> ConcessionPage:
    return await concessions.list_concessions(
        db, actor, student_id, academic_year_id, page, page_size
    )


@router.post(
    "/fees/concessions",
    response_model=ConcessionOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[_managers],
)
async def create_concession(
    data: ConcessionCreate, db: DbSession, actor: CurrentUser
) -> ConcessionOut:
    return await concessions.create_concession(db, actor, data)


@router.patch(
    "/fees/concessions/{concession_id}", response_model=ConcessionOut, dependencies=[_managers]
)
async def update_concession(
    concession_id: int, data: ConcessionUpdate, db: DbSession, actor: CurrentUser
) -> ConcessionOut:
    return await concessions.update_concession(db, actor, concession_id, data)


# ---- late fees ----


@router.post(
    "/fees/late-fees/preview", response_model=LateFeePreview, dependencies=[_managers]
)
async def preview_late_fees(
    db: DbSession, actor: CurrentUser, academic_year_id: int
) -> LateFeePreview:
    return await late_fees.preview(db, actor, academic_year_id)


@router.post("/fees/late-fees/apply", response_model=LateFeeResult, dependencies=[_managers])
async def apply_late_fees(data: LateFeeApply, db: DbSession, actor: CurrentUser) -> LateFeeResult:
    return await late_fees.apply(db, actor, data)


# ---- reminders ----


def _filters(
    academic_year_id: int | None,
    min_balance_paise: int,
    overdue_only: bool,
    days_before_due: int | None,
    class_id: int | None,
) -> reminders.ReminderFilters:
    return reminders.ReminderFilters(
        academic_year_id=academic_year_id,
        min_balance_paise=min_balance_paise,
        overdue_only=overdue_only,
        days_before_due=days_before_due,
        class_id=class_id,
    )


@router.get("/fees/reminders", response_model=ReminderPage, dependencies=[_readers])
async def list_reminders(
    db: DbSession,
    actor: CurrentUser,
    academic_year_id: int | None = None,
    min_balance_paise: Balance = 0,
    overdue_only: bool = True,
    days_before_due: DaysAhead = None,
    class_id: int | None = None,
    page: Page = 1,
    page_size: PageSize = 25,
) -> ReminderPage:
    f = _filters(academic_year_id, min_balance_paise, overdue_only, days_before_due, class_id)
    return await reminders.list_reminders(db, actor, f, page, page_size)


@router.get("/fees/reminders/export", dependencies=[_readers])
async def export_reminders(
    db: DbSession,
    actor: CurrentUser,
    academic_year_id: int | None = None,
    min_balance_paise: Balance = 0,
    overdue_only: bool = True,
    days_before_due: DaysAhead = None,
    class_id: int | None = None,
) -> Response:
    f = _filters(academic_year_id, min_balance_paise, overdue_only, days_before_due, class_id)
    content = await reminders.reminders_csv(db, actor, f)
    return Response(
        content=content,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="fee-reminders.csv"'},
    )


@router.post("/fees/reminders/mark", response_model=ReminderMarked, dependencies=[_managers])
async def mark_reminded(data: ReminderMark, db: DbSession, actor: CurrentUser) -> ReminderMarked:
    return await reminders.mark_reminded(db, actor, data.student_ids)
