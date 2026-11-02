from datetime import date as Date  # noqa: N812 - several params are named `date`
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status

from app.core.deps import CurrentUser, DbSession, require_roles
from app.modules.attendance import service
from app.modules.attendance.schemas import (
    DailySummary,
    HolidayCreate,
    HolidayOut,
    Sheet,
    SheetSave,
    StaffAttendanceSummary,
    StaffSave,
    StaffSheet,
    StudentAttendance,
)
from app.modules.settings.deps import require_feature
from app.modules.users.models import Role

router = APIRouter(tags=["attendance"], dependencies=[Depends(require_feature("attendance"))])

_writers = Depends(
    require_roles(Role.SCHOOL_OWNER, Role.MANAGEMENT, Role.HEADMASTER, Role.TEACHER, Role.CLERK)
)
_readers = Depends(
    require_roles(
        Role.SUPER_ADMIN,
        Role.SCHOOL_OWNER,
        Role.MANAGEMENT,
        Role.HEADMASTER,
        Role.TEACHER,
        Role.CLERK,
        Role.ACCOUNTANT,
    )
)
_staff_admins = Depends(
    require_roles(Role.SCHOOL_OWNER, Role.MANAGEMENT, Role.HEADMASTER, Role.CLERK)
)
_holiday_writers = Depends(require_roles(Role.SCHOOL_OWNER, Role.MANAGEMENT, Role.HEADMASTER))

# `from`/`to` are reserved-ish names in the API, so they are exposed through aliases.
FromQ = Annotated[Date | None, Query(alias="from")]
ToQ = Annotated[Date | None, Query()]
DayQ = Annotated[Date | None, Query(alias="date")]


def _day(day: Date | None) -> Date:
    return day or service.today()


# ---- student attendance ----


@router.get("/attendance/sheet", response_model=Sheet, dependencies=[_readers])
async def get_sheet(
    db: DbSession, actor: CurrentUser, section_id: Annotated[int, Query()], day: DayQ = None
) -> Sheet:
    return await service.get_sheet(db, actor, section_id, _day(day))


@router.put("/attendance/sheet", response_model=Sheet, dependencies=[_writers])
async def save_sheet(data: SheetSave, db: DbSession, actor: CurrentUser) -> Sheet:
    return await service.save_sheet(db, actor, data.section_id, data.date, data.entries)


@router.get("/attendance/daily-summary", response_model=DailySummary, dependencies=[_readers])
async def daily_summary(
    db: DbSession, actor: CurrentUser, day: DayQ = None, branch_id: int | None = None
) -> DailySummary:
    return await service.daily_summary(db, actor, _day(day), branch_id)


@router.get("/attendance/export", dependencies=[_readers])
async def export_attendance(
    db: DbSession,
    actor: CurrentUser,
    section_id: Annotated[int, Query()],
    from_: FromQ = None,
    to: ToQ = None,
) -> Response:
    content, filename = await service.export_csv(db, actor, section_id, from_, to)
    return Response(
        content=content,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/students/{student_id}/attendance", response_model=StudentAttendance)
async def student_attendance(
    student_id: int, db: DbSession, actor: CurrentUser, from_: FromQ = None, to: ToQ = None
) -> StudentAttendance:
    return await service.student_attendance(db, actor, student_id, from_, to)


# ---- staff attendance ----


@router.get("/staff-attendance", response_model=StaffSheet, dependencies=[_staff_admins])
async def get_staff_sheet(
    db: DbSession, actor: CurrentUser, day: DayQ = None, branch_id: int | None = None
) -> StaffSheet:
    return await service.get_staff_sheet(db, actor, _day(day), branch_id)


@router.put("/staff-attendance", response_model=StaffSheet, dependencies=[_staff_admins])
async def save_staff_sheet(data: StaffSave, db: DbSession, actor: CurrentUser) -> StaffSheet:
    return await service.save_staff_sheet(db, actor, data.date, data.branch_id, data.entries)


@router.get("/staff-attendance/summary", response_model=StaffAttendanceSummary)
async def staff_summary(
    db: DbSession,
    actor: CurrentUser,
    user_id: Annotated[int, Query()],
    from_: FromQ = None,
    to: ToQ = None,
) -> StaffAttendanceSummary:
    return await service.staff_summary(db, actor, user_id, from_, to)


# ---- holidays ----


@router.get("/holidays", response_model=list[HolidayOut])
async def list_holidays(
    db: DbSession,
    actor: CurrentUser,
    from_: FromQ = None,
    to: ToQ = None,
    branch_id: int | None = None,
) -> list[HolidayOut]:
    rows = await service.list_holidays(db, actor, from_, to, branch_id)
    return [HolidayOut.model_validate(h) for h in rows]


@router.post(
    "/holidays",
    response_model=HolidayOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[_holiday_writers],
)
async def create_holiday(data: HolidayCreate, db: DbSession, actor: CurrentUser) -> HolidayOut:
    return HolidayOut.model_validate(await service.create_holiday(db, actor, data))


@router.delete(
    "/holidays/{holiday_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[_holiday_writers],
)
async def delete_holiday(holiday_id: int, db: DbSession, actor: CurrentUser) -> Response:
    await service.delete_holiday(db, actor, holiday_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
