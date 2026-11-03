from typing import Annotated, Any

from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    EmailStr,
    Field,
    StringConstraints,
    field_validator,
)

from app.core.schema_types import ImportRowError
from app.modules.users.identity import normalize_email, normalize_phone, normalize_username
from app.modules.users.models import Role


def _blank_to_none(v: Any) -> Any:
    if isinstance(v, str):
        return v.strip() or None
    return v


OptEmail = Annotated[EmailStr | None, BeforeValidator(_blank_to_none)]
_PhoneInput = Annotated[str, StringConstraints(max_length=30)] | None
OptPhone = Annotated[_PhoneInput, BeforeValidator(_blank_to_none)]


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    email: str | None
    full_name: str
    phone: str | None
    role: Role
    school_id: int | None
    branch_id: int | None
    is_active: bool
    must_change_password: bool
    is_locked: bool
    mfa_enabled: bool


class UserCreate(BaseModel):
    username: str = Field(min_length=1, max_length=254)
    email: OptEmail = None
    full_name: str = Field(min_length=1, max_length=200)
    phone: OptPhone = None
    # Policy (length, common passwords, no username or name) is checked by the service.
    password: str = Field(max_length=128)
    role: Role
    # Super admin must give school_id; school owner's school is implied.
    school_id: int | None = None
    # Required for branch-bound roles when the creator is not tied to one branch.
    branch_id: int | None = None

    @field_validator("username")
    @classmethod
    def _username(cls, v: str) -> str:
        return normalize_username(v)

    @field_validator("email")
    @classmethod
    def _email(cls, v: str | None) -> str | None:
        return None if v is None else normalize_email(v)

    @field_validator("phone")
    @classmethod
    def _phone(cls, v: str | None) -> str | None:
        return None if v is None else normalize_phone(v)


class UserUpdate(BaseModel):
    """The username is immutable; it is ignored if sent."""

    full_name: str | None = Field(default=None, min_length=1, max_length=200)
    email: OptEmail = None
    phone: OptPhone = None
    is_active: bool | None = None

    @field_validator("email")
    @classmethod
    def _email(cls, v: str | None) -> str | None:
        return None if v is None else normalize_email(v)

    @field_validator("phone")
    @classmethod
    def _phone(cls, v: str | None) -> str | None:
        return None if v is None else normalize_phone(v)


class UserImportRequest(BaseModel):
    """Bulk staff accounts. Rows: username, full_name, role, email?, mobile? (no passwords: each
    account gets a generated temporary password, returned once in the result)."""

    # Branch for branch-bound roles when the importer is not tied to one branch.
    branch_id: int | None = None
    # Super admin only, as on the single-account form.
    school_id: int | None = None
    dry_run: bool = False
    rows: list[dict[str, Any]] = Field(min_length=1, max_length=500)


class ImportCredential(BaseModel):
    username: str
    full_name: str
    role: Role
    temporary_password: str


class UserImportResult(BaseModel):
    created: int
    would_create: int = 0
    failed: int
    errors: list[ImportRowError]
    # Only on a real import, returned once: never stored, logged or audited.
    credentials: list[ImportCredential]


class PasswordReset(BaseModel):
    new_password: str = Field(max_length=128)
