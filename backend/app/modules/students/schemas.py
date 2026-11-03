import re
from datetime import date, timedelta
from typing import Annotated, Any, Literal

from pydantic import (
    BaseModel,
    BeforeValidator,
    EmailStr,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

from app.core.schema_types import ImportRowError
from app.modules.students.models import Gender, GuardianRelation, StudentStatus
from app.modules.users.identity import normalize_username

Name100 = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
Name200 = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
_PHONE_RE = re.compile(r"^[0-9+\- ]{7,20}$")
MAX_ADMISSION_DAYS_AHEAD = 366


def _blank_to_none(v: Any) -> Any:
    if isinstance(v, str) and not v.strip():
        return None
    return v.strip() if isinstance(v, str) else v


OptEmail = Annotated[EmailStr | None, BeforeValidator(_blank_to_none)]
OptText = Annotated[str | None, BeforeValidator(_blank_to_none)]


def _check_phone(v: str) -> str:
    v = v.strip()
    if not _PHONE_RE.match(v):
        raise ValueError("phone must be 7-20 characters: digits, +, spaces or dashes")
    return v


def _check_dob(v: date) -> date:
    if v >= date.today():
        raise ValueError("date_of_birth must be in the past")
    if v.year < 1950:
        raise ValueError("date_of_birth is too far in the past")
    return v


def _check_admission(v: date) -> date:
    if v > date.today() + timedelta(days=MAX_ADMISSION_DAYS_AHEAD):
        raise ValueError("admission_date is too far in the future")
    if v.year < 1950:
        raise ValueError("admission_date is too far in the past")
    return v


# ---- output ----


class EnrollmentOut(BaseModel):
    id: int
    student_id: int
    academic_year_id: int
    academic_year_name: str
    class_id: int
    class_name: str
    section_id: int | None
    section_name: str | None
    roll_no: int | None


class GuardianOut(BaseModel):
    id: int
    student_id: int
    full_name: str
    relation: GuardianRelation
    phone: str
    email: str | None
    is_primary: bool
    user_id: int | None
    has_login: bool


class PrimaryGuardianOut(BaseModel):
    full_name: str
    phone: str
    relation: GuardianRelation


class StudentOut(BaseModel):
    id: int
    school_id: int
    branch_id: int
    admission_no: str
    first_name: str
    last_name: str
    full_name: str
    gender: Gender
    date_of_birth: date
    admission_date: date
    status: StudentStatus
    user_id: int | None
    current_enrollment: EnrollmentOut | None
    primary_guardian: PrimaryGuardianOut | None


class StudentDetail(StudentOut):
    address: str | None
    previous_school: str | None
    guardians: list[GuardianOut]
    enrollments: list[EnrollmentOut]
    # Current parental consent per purpose: granted, refused, withdrawn or none.
    consent_status: dict[str, str] = {}


class StudentPage(BaseModel):
    items: list[StudentOut]
    total: int
    page: int
    page_size: int


class CredentialOut(BaseModel):
    """A login created or linked together with a student. Returned once, never stored in clear."""

    role: Literal["student", "parent"]
    full_name: str
    username: str
    temporary_password: str | None
    linked_existing: bool
    note: str | None


class StudentCreated(StudentDetail):
    credentials: list[CredentialOut] = []


class ParentChild(BaseModel):
    student_id: int
    full_name: str
    class_name: str | None


class ParentOut(BaseModel):
    id: int
    full_name: str
    username: str
    phone: str | None
    email: str | None
    children: list[ParentChild]


# ---- input ----


class GuardianCreate(BaseModel):
    full_name: Name200
    relation: GuardianRelation
    phone: str
    email: OptEmail = None
    is_primary: bool | None = None

    _phone = field_validator("phone")(_check_phone)


class NewGuardian(GuardianCreate):
    """A guardian sent with a new student: may link an existing parent login or get a new one."""

    existing_parent_user_id: int | None = Field(default=None, ge=1)
    # None means: true for the primary guardian when the request asks for logins, else false.
    create_login: bool | None = None


class GuardianUpdate(BaseModel):
    full_name: Name200 | None = None
    relation: GuardianRelation | None = None
    phone: str | None = None
    email: OptEmail = None
    is_primary: bool | None = None

    @field_validator("phone")
    @classmethod
    def _phone(cls, v: str | None) -> str | None:
        return None if v is None else _check_phone(v)


class EnrollmentIn(BaseModel):
    academic_year_id: int
    class_id: int
    section_id: int | None = None
    roll_no: int | None = Field(default=None, ge=1, le=999)


class StudentCreate(BaseModel):
    # Required unless the creator belongs to a single branch (then it is forced).
    branch_id: int | None = None
    first_name: Name100
    last_name: Name100
    gender: Gender
    date_of_birth: date
    admission_date: date | None = None
    admission_no: Annotated[str | None, BeforeValidator(_blank_to_none)] = Field(
        default=None, max_length=50
    )
    address: OptText = None
    previous_school: OptText = Field(default=None, max_length=200)
    guardians: list[NewGuardian] = Field(min_length=1, max_length=10)
    enrollment: EnrollmentIn | None = None
    create_student_login: bool = False

    _dob = field_validator("date_of_birth")(_check_dob)

    @field_validator("admission_date")
    @classmethod
    def _adm(cls, v: date | None) -> date | None:
        return None if v is None else _check_admission(v)

    @model_validator(mode="after")
    def _one_primary(self) -> "StudentCreate":
        if sum(1 for g in self.guardians if g.is_primary) > 1:
            raise ValueError("only one guardian can be primary")
        return self


class StudentUpdate(BaseModel):
    first_name: Name100 | None = None
    last_name: Name100 | None = None
    gender: Gender | None = None
    date_of_birth: date | None = None
    admission_date: date | None = None
    address: OptText = None
    previous_school: OptText = Field(default=None, max_length=200)
    status: StudentStatus | None = None

    @field_validator("date_of_birth")
    @classmethod
    def _dob(cls, v: date | None) -> date | None:
        return None if v is None else _check_dob(v)

    @field_validator("admission_date")
    @classmethod
    def _adm(cls, v: date | None) -> date | None:
        return None if v is None else _check_admission(v)


_OptUsername = Annotated[str, StringConstraints(max_length=254)] | None


class LoginCreate(BaseModel):
    """Username is optional: when omitted it is derived from the email's local part."""

    username: Annotated[_OptUsername, BeforeValidator(_blank_to_none)] = None
    email: OptEmail = None
    # Policy is checked by the service, which knows the derived username and the person's name.
    password: str = Field(max_length=128)

    @field_validator("username")
    @classmethod
    def _username(cls, v: str | None) -> str | None:
        return None if v is None else normalize_username(v)

    @model_validator(mode="after")
    def _need_handle(self) -> "LoginCreate":
        if self.username is None and self.email is None:
            raise ValueError("Give a username or an email")
        return self


class ImportRow(BaseModel):
    """One import row; validated per row so one bad row does not reject the whole request."""

    first_name: Name100
    last_name: Name100
    gender: Gender
    date_of_birth: date
    admission_date: date | None = None
    admission_no: Annotated[str | None, BeforeValidator(_blank_to_none)] = Field(
        default=None, max_length=50
    )
    address: OptText = None
    guardian_name: Name200
    guardian_phone: str
    guardian_relation: Annotated[
        GuardianRelation, BeforeValidator(lambda v: _blank_to_none(v) or "guardian")
    ] = GuardianRelation.GUARDIAN
    class_: Annotated[str | None, BeforeValidator(_blank_to_none)] = Field(
        default=None, alias="class"
    )
    section: Annotated[str | None, BeforeValidator(_blank_to_none)] = None
    roll_no: Annotated[
        int | None, BeforeValidator(lambda v: None if v in ("", None) else v)
    ] = Field(default=None, ge=1, le=999)

    _phone = field_validator("guardian_phone")(_check_phone)
    _dob = field_validator("date_of_birth")(_check_dob)

    @field_validator("admission_date")
    @classmethod
    def _adm(cls, v: date | None) -> date | None:
        return None if v is None else _check_admission(v)


class ImportRequest(BaseModel):
    branch_id: int | None = None
    academic_year_id: int | None = None
    # Validate every row exactly as a real import would, then write nothing.
    dry_run: bool = False
    rows: list[dict[str, Any]] = Field(min_length=1, max_length=500)


class ImportResult(BaseModel):
    created: int
    # Rows a real import would create (dry run only; 0 otherwise).
    would_create: int = 0
    failed: int
    errors: list[ImportRowError]


# ---- government identifiers (PEN, APAAR) ----

PenStr = (
    Annotated[
        str,
        StringConstraints(
            strip_whitespace=True, min_length=11, max_length=11, pattern=r"^[A-Za-z0-9]{11}$"
        ),
    ]
    | None
)
ApaarStr = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=12, max_length=12, pattern=r"^[0-9]{12}$"),
] | None


class IdentifiersOut(BaseModel):
    """Masked identifiers: only the last 3 characters of each value are shown."""

    enabled: bool
    pen_masked: str | None = None
    apaar_masked: str | None = None
    apaar_consent: bool | None = None
    aadhaar_details_match: bool | None = None


class IdentifiersRevealed(BaseModel):
    """Full identifier values. Only school owners, management and headmasters may read these."""

    pen: str | None
    apaar_id: str | None
    apaar_consent: bool | None
    aadhaar_details_match: bool | None


class IdentifiersIn(BaseModel):
    """Partial update: fields not sent are left as they are; an explicit null clears a value."""

    pen: PenStr = None
    apaar_id: ApaarStr = None
    apaar_consent: bool | None = None
    aadhaar_details_match: bool | None = None
