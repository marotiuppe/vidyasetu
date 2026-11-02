from datetime import date
from typing import Annotated, Any

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, StringConstraints

from app.modules.attendance.models import AttendanceStatus, StaffStatus

MAX_ENTRIES = 200


def _blank_to_none(v: Any) -> Any:
    if isinstance(v, str):
        return v.strip() or None
    return v


# The length rule must apply to the string only, so an explicit `null` remark is accepted.
Remark = Annotated[
    Annotated[str, StringConstraints(max_length=200)] | None, BeforeValidator(_blank_to_none)
]
HolidayName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]


class _Out(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


# ---- student attendance ----


class SheetEntryIn(BaseModel):
    student_id: int
    status: AttendanceStatus
    remark: Remark = None


class SheetSave(BaseModel):
    section_id: int
    date: date
    entries: list[SheetEntryIn] = Field(max_length=MAX_ENTRIES)


class SheetStudent(_Out):
    student_id: int
    admission_no: str
    full_name: str
    roll_no: int | None
    status: str | None
    remark: str | None


class Counts(_Out):
    total: int
    present: int
    absent: int
    leave: int
    unmarked: int


class Sheet(_Out):
    section_id: int
    section_name: str
    class_id: int
    class_name: str
    branch_id: int
    date: date
    academic_year_id: int
    is_working_day: bool
    non_working_reason: str | None
    students: list[SheetStudent]
    summary: Counts


class SectionSummary(Counts):
    branch_id: int
    class_id: int
    class_name: str
    section_id: int
    section_name: str
    is_working_day: bool


class DailySummary(_Out):
    date: date
    is_working_day: bool
    non_working_reason: str | None
    sections: list[SectionSummary]
    totals: Counts


class DayRecord(_Out):
    date: date
    status: str
    remark: str | None


class StudentSummary(_Out):
    present: int
    absent: int
    leave: int
    marked_days: int
    percentage: float | None


class StudentAttendance(_Out):
    student_id: int
    from_: date = Field(alias="from")
    to: date
    records: list[DayRecord]
    summary: StudentSummary


# ---- staff attendance ----


class StaffEntryIn(BaseModel):
    user_id: int
    status: StaffStatus
    remark: Remark = None


class StaffSave(BaseModel):
    date: date
    branch_id: int | None = None
    entries: list[StaffEntryIn] = Field(max_length=MAX_ENTRIES)


class StaffRow(_Out):
    user_id: int
    full_name: str
    role: str
    branch_id: int | None
    status: str | None
    remark: str | None


class StaffSheet(_Out):
    date: date
    is_working_day: bool
    non_working_reason: str | None
    staff: list[StaffRow]


class StaffSummaryCounts(_Out):
    present: int
    absent: int
    leave: int
    half_day: int
    marked_days: int
    percentage: float | None


class StaffAttendanceSummary(_Out):
    user_id: int
    from_: date = Field(alias="from")
    to: date
    records: list[DayRecord]
    summary: StaffSummaryCounts


# ---- holidays ----


class HolidayCreate(BaseModel):
    date: date
    name: HolidayName
    branch_id: int | None = None


class HolidayOut(_Out):
    id: int
    school_id: int
    branch_id: int | None
    date: date
    name: str
