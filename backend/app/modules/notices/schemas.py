from datetime import date
from typing import Annotated, Self

from pydantic import BaseModel, StringConstraints, model_validator

from app.core.schema_types import UtcDateTime
from app.modules.notices.models import NoticeCategory, TargetType

Title = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=150)]
Body = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=5000)]


class TargetIn(BaseModel):
    type: TargetType
    branch_id: int | None = None
    class_id: int | None = None
    section_id: int | None = None


class NoticeCreate(BaseModel):
    title: Title
    body: Body
    category: NoticeCategory = NoticeCategory.GENERAL
    is_pinned: bool | None = None
    expires_on: date | None = None
    target: TargetIn


class NoticeUpdate(BaseModel):
    title: Title | None = None
    body: Body | None = None
    category: NoticeCategory | None = None
    is_pinned: bool | None = None
    expires_on: date | None = None  # explicit null clears the expiry

    @model_validator(mode="after")
    def _no_null_required(self) -> Self:
        for name in ("title", "body", "category", "is_pinned"):
            if name in self.model_fields_set and getattr(self, name) is None:
                raise ValueError(f"{name} cannot be null")
        return self


class Author(BaseModel):
    id: int
    full_name: str
    role: str


class NoticeOut(BaseModel):
    id: int
    title: str
    body: str
    category: NoticeCategory
    is_pinned: bool
    expires_on: date | None
    is_expired: bool
    target_type: TargetType
    target_label: str
    branch_id: int | None
    class_id: int | None
    section_id: int | None
    author: Author | None
    created_at: UtcDateTime
    is_read: bool
    read_count: int | None
    can_edit: bool


class NoticePage(BaseModel):
    items: list[NoticeOut]
    total: int
    page: int
    page_size: int
    unread_count: int


class UnreadCount(BaseModel):
    count: int
