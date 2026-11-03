from datetime import date
from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
)

from app.core.schema_types import UtcDateTime
from app.modules.admissions.models import ApplicationSource, ApplicationStatus
from app.modules.students.models import Gender, GuardianRelation
from app.modules.students.schemas import (
    CredentialOut,
    Name100,
    Name200,
    OptEmail,
    _check_dob,
    _check_phone,
)

Text500 = Annotated[
    Annotated[str, StringConstraints(strip_whitespace=True, max_length=500)] | None,
    BeforeValidator(lambda v: (v.strip() or None) if isinstance(v, str) else v),
]
Text1000 = Annotated[
    Annotated[str, StringConstraints(strip_whitespace=True, max_length=1000)] | None,
    BeforeValidator(lambda v: (v.strip() or None) if isinstance(v, str) else v),
]
School200 = Annotated[
    Annotated[str, StringConstraints(strip_whitespace=True, max_length=200)] | None,
    BeforeValidator(lambda v: (v.strip() or None) if isinstance(v, str) else v),
]
AdmissionNo = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=50)
]
DocName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]


# ---- output ----


class AppOut(BaseModel):
    id: int
    school_id: int
    branch_id: int
    branch_name: str
    first_name: str
    last_name: str
    gender: Gender | None
    date_of_birth: date | None
    class_id: int | None
    class_name: str | None
    academic_year_id: int | None
    guardian_name: str
    guardian_phone: str
    guardian_email: str | None
    guardian_relation: GuardianRelation
    address: str | None
    previous_school: str | None
    source: ApplicationSource
    status: ApplicationStatus
    notes: str | None
    rejection_reason: str | None
    student_id: int | None
    created_by: int | None
    privacy_notice_accepted_at: UtcDateTime | None
    created_at: UtcDateTime
    updated_at: UtcDateTime


class DocOut(BaseModel):
    id: int
    name: str
    content_type: str
    size_bytes: int
    created_at: UtcDateTime


class AppDetail(AppOut):
    documents: list[DocOut]


class AppPage(BaseModel):
    items: list[AppOut]
    total: int
    page: int
    page_size: int


class SummaryOut(BaseModel):
    """Number of applications per status, within the caller's scope."""

    total: int
    enquiry: int
    applied: int
    admitted: int
    rejected: int
    enrolled: int


class ConvertResult(BaseModel):
    student_id: int
    credentials: list[CredentialOut] = []


class PublicClass(BaseModel):
    id: int
    branch_id: int
    name: str


class PublicBranch(BaseModel):
    id: int
    name: str


class PublicAdmissions(BaseModel):
    school_name: str
    branches: list[PublicBranch]
    classes: list[PublicClass]
    open: bool


class PublicReference(BaseModel):
    reference: str


# ---- input ----


class AppCreate(BaseModel):
    """Staff-created applicant. `branch_id` is required for school owners and taken from the
    token for branch-level staff."""

    branch_id: int | None = Field(default=None, ge=1)
    first_name: Name100
    last_name: Name100
    gender: Gender | None = None
    date_of_birth: date | None = None
    class_id: int | None = Field(default=None, ge=1)
    academic_year_id: int | None = Field(default=None, ge=1)
    guardian_name: Name200
    guardian_phone: str
    guardian_email: OptEmail = None
    guardian_relation: GuardianRelation = GuardianRelation.GUARDIAN
    address: Text500 = None
    previous_school: School200 = None
    source: Literal["enquiry", "walk_in"] = "walk_in"
    notes: Text1000 = None

    _phone = field_validator("guardian_phone")(_check_phone)

    @field_validator("date_of_birth")
    @classmethod
    def _dob(cls, v: date | None) -> date | None:
        return None if v is None else _check_dob(v)


class AppUpdate(BaseModel):
    """Every field optional. Status and the converted student cannot be changed here."""

    model_config = ConfigDict(extra="forbid")

    first_name: Name100 | None = None
    last_name: Name100 | None = None
    gender: Gender | None = None
    date_of_birth: date | None = None
    class_id: int | None = Field(default=None, ge=1)
    academic_year_id: int | None = Field(default=None, ge=1)
    guardian_name: Name200 | None = None
    guardian_phone: str | None = None
    guardian_email: OptEmail = None
    guardian_relation: GuardianRelation | None = None
    address: Text500 = None
    previous_school: School200 = None
    notes: Text1000 = None

    @field_validator("guardian_phone")
    @classmethod
    def _phone(cls, v: str | None) -> str | None:
        return None if v is None else _check_phone(v)

    @field_validator("date_of_birth")
    @classmethod
    def _dob(cls, v: date | None) -> date | None:
        return None if v is None else _check_dob(v)


class StatusChange(BaseModel):
    status: ApplicationStatus
    reason: Annotated[str, StringConstraints(strip_whitespace=True, max_length=500)] | None = None


class ConvertRequest(BaseModel):
    class_id: int = Field(ge=1)
    section_id: int | None = Field(default=None, ge=1)
    academic_year_id: int = Field(ge=1)
    admission_no: AdmissionNo
    admission_date: date | None = None


class PublicApply(BaseModel):
    """The public online form. Unknown fields are refused; `website` is a honeypot (must stay
    empty); `consent` must be true (the guardian agreed to the privacy notice)."""

    model_config = ConfigDict(extra="forbid")

    branch_id: int = Field(ge=1)
    class_id: int | None = Field(default=None, ge=1)
    first_name: Name100
    last_name: Name100
    gender: Gender | None = None
    date_of_birth: date | None = None
    guardian_name: Name200
    guardian_phone: str
    guardian_email: OptEmail = None
    guardian_relation: GuardianRelation
    address: Text500 = None
    previous_school: School200 = None
    consent: Literal[True]
    website: Annotated[str, StringConstraints(max_length=200)] = ""

    _phone = field_validator("guardian_phone")(_check_phone)

    @field_validator("date_of_birth")
    @classmethod
    def _dob(cls, v: date | None) -> date | None:
        return None if v is None else _check_dob(v)
