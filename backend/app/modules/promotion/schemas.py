from datetime import date
from typing import Annotated

from pydantic import BaseModel, Field

from app.core.schema_types import UtcDateTime
from app.modules.promotion.models import PromotionAction
from app.modules.students.models import StudentStatus

MAX_ITEMS = 500
MAX_CANDIDATES = 500

Id = Annotated[int, Field(ge=1)]


class PreviewRequest(BaseModel):
    from_year_id: Id
    to_year_id: Id
    class_id: Id
    section_id: Id | None = None


class CandidateOut(BaseModel):
    student_id: int
    name: str
    admission_no: str
    roll_no: int | None
    from_class: str
    from_section: str | None
    suggested_action: PromotionAction
    # Hidden (None) for branch-level staff when the suggestion is in another branch.
    suggested_to_class_id: int | None
    suggested_to_class_name: str | None
    suggested_to_branch_name: str | None
    needs_owner: bool
    dues_paise: int
    already_enrolled: bool


class ClassOption(BaseModel):
    id: int
    name: str
    branch_id: int
    branch_name: str
    level: int


class SectionOption(BaseModel):
    id: int
    class_id: int
    name: str


class PreviewOut(BaseModel):
    candidates: list[CandidateOut]
    truncated: bool
    class_options: list[ClassOption]
    sections: list[SectionOption]


class ApplyItem(BaseModel):
    student_id: Id
    action: PromotionAction
    to_class_id: Id | None = None
    to_section_id: Id | None = None


class ApplyRequest(BaseModel):
    from_year_id: Id
    to_year_id: Id
    carry_over: bool = False
    due_date: date | None = None
    items: list[ApplyItem] = Field(min_length=1, max_length=MAX_ITEMS)


class SkippedOut(BaseModel):
    student_id: int
    reason: str


class Counts(BaseModel):
    promoted: int
    detained: int
    left: int
    passed_out: int
    transferred: int
    carried_invoices: int
    carried_paise: int


class BatchOut(Counts):
    id: int
    from_year_id: int
    to_year_id: int
    carry_over: bool
    created_at: UtcDateTime
    undo_until: UtcDateTime
    undone_at: UtcDateTime | None
    skipped: list[SkippedOut] = []


class BatchItemOut(BaseModel):
    student_id: int
    name: str
    action: PromotionAction
    from_class: str | None
    to_class: str | None
    carried_paise: int
    from_status: StudentStatus
    to_status: StudentStatus


class BatchDetail(BatchOut):
    items: list[BatchItemOut]
