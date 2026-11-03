"""Schemas for the fee tools: concessions, late fees and reminders."""

from datetime import date
from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from app.core.schema_types import UtcDateTime
from app.modules.fees.models import ConcessionKind
from app.modules.fees.schemas import MAX_PAISE, _reject_nulls

ConcessionName = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)
]
ConcessionReason = Annotated[str, StringConstraints(strip_whitespace=True, max_length=200)]
ConcessionValue = Annotated[int, Field(strict=True, ge=0, le=MAX_PAISE)]
BASIS_POINTS_MAX = 10_000


def _check_value(kind: ConcessionKind, value: int) -> None:
    if value <= 0:
        raise ValueError("value must be more than zero")
    if kind == ConcessionKind.PERCENT and value > BASIS_POINTS_MAX:
        raise ValueError("a percent concession cannot exceed 100% (10000 basis points)")


# ---- concessions ----


class ConcessionCreate(BaseModel):
    student_id: int
    academic_year_id: int
    name: ConcessionName
    kind: ConcessionKind
    value: ConcessionValue
    fee_head_id: int | None = None
    reason: Annotated[str, StringConstraints(strip_whitespace=True, max_length=200)] | None = None

    @model_validator(mode="after")
    def _valid_value(self) -> Self:
        _check_value(self.kind, self.value)
        return self


class ConcessionUpdate(BaseModel):
    name: ConcessionName | None = None
    value: ConcessionValue | None = None
    reason: ConcessionReason | None = None  # explicit null clears
    active: bool | None = None

    @model_validator(mode="after")
    def _no_null(self) -> Self:
        _reject_nulls(self, "name", "value", "active")
        return self


class ConcessionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    student_id: int
    student_name: str
    admission_no: str
    academic_year_id: int
    name: str
    kind: ConcessionKind
    value: int
    fee_head_id: int | None
    fee_head_name: str | None
    reason: str | None
    active: bool
    created_at: UtcDateTime


class ConcessionPage(BaseModel):
    items: list[ConcessionOut]
    total: int
    page: int
    page_size: int


# ---- late fees ----


class LateFeeRow(BaseModel):
    invoice_id: int
    invoice_no: str
    student_id: int
    student_name: str
    admission_no: str
    class_name: str | None
    title: str
    due_date: date
    balance_paise: int
    late_fee_paise: int


class LateFeePreview(BaseModel):
    enabled: bool
    late_fee_type: str
    items: list[LateFeeRow]
    count: int
    total_late_fee_paise: int


class LateFeeApply(BaseModel):
    academic_year_id: int
    invoice_ids: Annotated[list[int], Field(max_length=500)] | None = None

    @model_validator(mode="after")
    def _non_empty(self) -> Self:
        if self.invoice_ids is not None and not self.invoice_ids:
            raise ValueError("Select at least one invoice, or leave invoice_ids out for all")
        return self


class LateFeeResult(BaseModel):
    created: int
    skipped: int


# ---- reminders ----


class ReminderRow(BaseModel):
    student_id: int
    student_name: str
    admission_no: str
    class_name: str | None
    guardian_name: str | None
    guardian_phone: str | None
    balance_paise: int
    overdue_paise: int
    oldest_due_date: date | None
    last_reminded_at: UtcDateTime | None
    reminder_count: int


class ReminderPage(BaseModel):
    items: list[ReminderRow]
    total: int
    page: int
    page_size: int


class ReminderMark(BaseModel):
    student_ids: Annotated[list[int], Field(min_length=1, max_length=200)]


class ReminderMarked(BaseModel):
    marked: int
