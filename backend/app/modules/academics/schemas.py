from datetime import date

from pydantic import BaseModel, ConfigDict, Field, model_validator


class AcademicYearOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    school_id: int
    name: str
    start_date: date
    end_date: date
    is_current: bool


class AcademicYearCreate(BaseModel):
    name: str = Field(min_length=1, max_length=20)
    start_date: date
    end_date: date
    is_current: bool = False
    school_id: int | None = None  # only used by the platform super admin

    @model_validator(mode="after")
    def _dates(self) -> "AcademicYearCreate":
        if self.end_date <= self.start_date:
            raise ValueError("end_date must be after start_date")
        return self


class AcademicYearUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=20)
    start_date: date | None = None
    end_date: date | None = None
    is_current: bool | None = None


class ClassOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    school_id: int
    branch_id: int
    name: str
    level: int


class ClassCreate(BaseModel):
    name: str = Field(min_length=1, max_length=50)
    level: int = Field(ge=1, le=12)
    # Required unless the creator belongs to a single branch.
    branch_id: int | None = None


class ClassUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=50)
    level: int | None = Field(default=None, ge=1, le=12)


class SectionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    school_id: int
    branch_id: int
    class_id: int
    name: str


class SectionCreate(BaseModel):
    class_id: int
    name: str = Field(min_length=1, max_length=20)


class SectionUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=20)
