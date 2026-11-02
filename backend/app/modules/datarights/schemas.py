from datetime import date
from typing import Annotated

from pydantic import BaseModel, StringConstraints

from app.core.schema_types import UtcDateTime
from app.modules.datarights.models import RequestStatus, RequestType

Message = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]
Note = Annotated[str, StringConstraints(strip_whitespace=True, max_length=2000)]


class DataRequestCreate(BaseModel):
    type: RequestType
    message: Message
    # A parent may name one of their linked children; everyone else asks about themselves.
    student_id: int | None = None


class DataRequestUpdate(BaseModel):
    status: RequestStatus
    response_note: Note | None = None


class DataRequestOut(BaseModel):
    id: int
    type: RequestType
    status: RequestStatus
    message: str
    response_note: str | None
    student_id: int | None
    student_name: str | None
    requester_user_id: int
    requester_name: str | None
    requester_role: str | None
    handled_by_user_id: int | None
    created_at: UtcDateTime
    updated_at: UtcDateTime
    due_on: date
    overdue: bool


class DataRequestPage(BaseModel):
    items: list[DataRequestOut]
    total: int
    page: int
    page_size: int
