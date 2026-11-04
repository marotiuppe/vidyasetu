"""Request and response schemas for homework."""

from datetime import date
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

Title = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=150)]
# The length limit sits on the str inside the union so an explicit null never reaches it.
OptTitle = (
    Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=150)] | None
)
OptDescription = Annotated[str, StringConstraints(strip_whitespace=True, max_length=4000)] | None


class _In(BaseModel):
    model_config = ConfigDict(extra="forbid")


class HomeworkIn(_In):
    section_id: int = Field(ge=1)
    subject_id: int = Field(ge=1)
    title: Title
    description: OptDescription = None
    assigned_on: date | None = None  # defaults to today (IST)
    due_date: date
    academic_year_id: int | None = Field(default=None, ge=1)  # defaults to the current year


class HomeworkPatch(_In):
    section_id: int | None = Field(default=None, ge=1)
    subject_id: int | None = Field(default=None, ge=1)
    title: OptTitle = None
    description: OptDescription = None
    assigned_on: date | None = None
    due_date: date | None = None


class HomeworkOut(BaseModel):
    id: int
    branch_id: int
    academic_year_id: int
    section_id: int
    section_name: str
    class_id: int
    class_name: str
    subject_id: int
    subject_name: str
    teacher_id: int
    teacher_name: str
    title: str
    description: str | None
    assigned_on: date
    due_date: date


class HomeworkPage(BaseModel):
    items: list[HomeworkOut]
    total: int
    page: int
    page_size: int
