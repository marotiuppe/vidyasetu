"""Request and response schemas for the timetable. Times leave the API as "HH:MM"."""

from datetime import time
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, PlainSerializer, StringConstraints

Name50 = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=50)]
# Optional text: the constraint sits on the str inside the union so an explicit null never
# reaches the length check.
OptName50 = (
    Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=50)] | None
)
OptRoom = Annotated[str, StringConstraints(strip_whitespace=True, max_length=30)] | None

HHMM = Annotated[time, PlainSerializer(lambda t: t.strftime("%H:%M"), when_used="json")]


class _In(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PeriodIn(_In):
    name: Name50
    sequence: int = Field(ge=1, le=30)
    start_time: time
    end_time: time
    is_break: bool = False


class PeriodPatch(_In):
    name: OptName50 = None
    sequence: int | None = Field(default=None, ge=1, le=30)
    start_time: time | None = None
    end_time: time | None = None
    is_break: bool | None = None


class PeriodOut(BaseModel):
    id: int
    branch_id: int
    name: str
    sequence: int
    start_time: HHMM
    end_time: HHMM
    is_break: bool


class EntryPut(_In):
    section_id: int = Field(ge=1)
    academic_year_id: int = Field(ge=1)
    weekday: int = Field(ge=1, le=7)
    period_id: int = Field(ge=1)
    subject_id: int = Field(ge=1)
    teacher_id: int | None = Field(default=None, ge=1)
    room: OptRoom = None


class EntryOut(BaseModel):
    """A cell of one section's week."""

    id: int
    section_id: int
    academic_year_id: int
    weekday: int
    period_id: int
    subject_id: int
    subject_name: str
    teacher_id: int | None
    teacher_name: str | None
    room: str | None


class SectionRef(BaseModel):
    id: int
    name: str
    class_id: int
    class_name: str


class SectionWeekOut(BaseModel):
    section: SectionRef
    academic_year_id: int
    periods: list[PeriodOut]
    entries: list[EntryOut]


class PersonEntryOut(BaseModel):
    """A cell of a teacher's week: which section and subject they teach."""

    id: int
    weekday: int
    period_id: int
    subject_id: int
    subject_name: str
    section_id: int
    section_name: str
    class_id: int
    class_name: str
    room: str | None


class TeacherRef(BaseModel):
    id: int
    full_name: str


class TeacherWeekOut(BaseModel):
    teacher: TeacherRef
    academic_year_id: int
    periods: list[PeriodOut]
    entries: list[PersonEntryOut]


class StudentRef(BaseModel):
    id: int
    full_name: str


class StudentWeekOut(BaseModel):
    student: StudentRef
    academic_year_id: int
    section: SectionRef | None
    periods: list[PeriodOut]
    entries: list[EntryOut]
