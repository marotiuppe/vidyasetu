from datetime import date
from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from app.core.schema_types import UtcDateTime
from app.modules.fees.models import PaymentMethod, PaymentStatus

MAX_PAISE = 10_000_000_00  # per single amount

# Integer paise only (strict: no floats, no numeric strings, no booleans).
Paise = Annotated[int, Field(strict=True, ge=0, le=MAX_PAISE)]
PositivePaise = Annotated[int, Field(strict=True, gt=0, le=MAX_PAISE)]

HeadName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
Title = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
Description = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=150)]
Reason = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
Reference = Annotated[str, StringConstraints(strip_whitespace=True, max_length=100)]
Note = Annotated[str, StringConstraints(strip_whitespace=True, max_length=200)]
DiscountReason = Annotated[str, StringConstraints(strip_whitespace=True, max_length=200)]


def _reject_nulls(model: BaseModel, *names: str) -> None:
    for name in names:
        if name in model.model_fields_set and getattr(model, name) is None:
            raise ValueError(f"{name} cannot be null")


# ---- heads ----


class HeadCreate(BaseModel):
    name: HeadName


class HeadUpdate(BaseModel):
    name: HeadName | None = None
    is_active: bool | None = None

    @model_validator(mode="after")
    def _no_null(self) -> Self:
        _reject_nulls(self, "name", "is_active")
        return self


class HeadOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    is_active: bool


# ---- structure ----


class StructureItemIn(BaseModel):
    fee_head_id: int
    amount_paise: Paise


class StructureReplace(BaseModel):
    academic_year_id: int
    class_id: int
    items: Annotated[list[StructureItemIn], Field(max_length=30)]


class StructureItemOut(BaseModel):
    id: int
    academic_year_id: int
    class_id: int
    class_name: str
    fee_head_id: int
    fee_head_name: str
    amount_paise: int


# ---- invoices ----


class GenerateRequest(BaseModel):
    academic_year_id: int
    title: Title
    due_date: date
    class_id: int | None = None
    section_id: int | None = None
    student_ids: Annotated[list[int], Field(max_length=1000)] | None = None
    fee_head_ids: Annotated[list[int], Field(max_length=100)] | None = None

    @model_validator(mode="after")
    def _need_target(self) -> Self:
        if self.class_id is None and self.section_id is None and not self.student_ids:
            raise ValueError("Provide class_id, section_id or student_ids")
        return self


class GenerateResult(BaseModel):
    created: int
    skipped_existing: int
    skipped_no_structure: int


class LineIn(BaseModel):
    description: Description
    fee_head_id: int | None = None
    amount_paise: Paise


class InvoiceCreate(BaseModel):
    student_id: int
    academic_year_id: int
    title: Title
    due_date: date
    lines: Annotated[list[LineIn], Field(min_length=1, max_length=30)]


class InvoiceUpdate(BaseModel):
    due_date: date | None = None
    discount_paise: Paise | None = None
    discount_reason: DiscountReason | None = None  # explicit null clears

    @model_validator(mode="after")
    def _no_null(self) -> Self:
        _reject_nulls(self, "due_date", "discount_paise")
        return self


class CancelRequest(BaseModel):
    reason: Reason


class LineOut(BaseModel):
    id: int
    fee_head_id: int | None
    description: str
    amount_paise: int


class PaymentCreate(BaseModel):
    amount_paise: PositivePaise
    method: PaymentMethod
    reference: Reference | None = None
    paid_on: date | None = None
    note: Note | None = None


class ReverseRequest(BaseModel):
    reason: Reason


class PaymentOut(BaseModel):
    id: int
    receipt_no: str
    invoice_id: int
    invoice_no: str
    student_id: int
    student_name: str
    amount_paise: int
    method: PaymentMethod
    reference: str | None
    paid_on: date
    status: PaymentStatus
    received_by_name: str
    note: str | None
    reversed_reason: str | None
    created_at: UtcDateTime


class InvoiceOut(BaseModel):
    id: int
    invoice_no: str
    student_id: int
    student_name: str
    admission_no: str
    class_name: str | None
    section_name: str | None
    academic_year_id: int
    title: str
    due_date: date
    gross_paise: int
    discount_paise: int
    discount_reason: str | None
    total_paise: int
    carried_forward_paise: int = 0
    paid_paise: int
    balance_paise: int
    status: str
    is_overdue: bool


class InvoiceDetail(InvoiceOut):
    lines: list[LineOut]
    payments: list[PaymentOut]
    cancel_reason: str | None


class Totals(BaseModel):
    billed_paise: int
    paid_paise: int
    balance_paise: int


class InvoicePage(BaseModel):
    items: list[InvoiceOut]
    total: int
    page: int
    page_size: int
    totals: Totals


class PaymentTotals(BaseModel):
    received_paise: int


class PaymentPage(BaseModel):
    items: list[PaymentOut]
    total: int
    page: int
    page_size: int
    totals: PaymentTotals


# ---- dues / collection / student view ----


class DueRow(BaseModel):
    student_id: int
    student_name: str
    admission_no: str
    class_name: str | None
    section_name: str | None
    guardian_name: str | None
    guardian_phone: str | None
    billed_paise: int
    paid_paise: int
    balance_paise: int
    overdue_paise: int
    oldest_due_date: date | None


class DueTotals(BaseModel):
    billed_paise: int
    paid_paise: int
    balance_paise: int
    overdue_paise: int


class DuesOut(BaseModel):
    items: list[DueRow]
    totals: DueTotals


class MethodTotal(BaseModel):
    method: PaymentMethod
    total_paise: int
    count: int


class DayTotal(BaseModel):
    date: date
    total_paise: int


class CollectionOut(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    from_: date = Field(alias="from")
    to: date
    total_paise: int
    count: int
    by_method: list[MethodTotal]
    by_day: list[DayTotal]


class StudentFees(BaseModel):
    student_id: int
    invoices: list[InvoiceDetail]
    summary: Totals
