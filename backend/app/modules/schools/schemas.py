from typing import Annotated

from pydantic import BaseModel, ConfigDict, EmailStr, Field, StringConstraints, field_validator

from app.modules.users.identity import normalize_username

_Name = Annotated[str, StringConstraints(min_length=1, max_length=200)]
_Board = Annotated[str, StringConstraints(max_length=50)]


class SchoolOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    code: str
    board: str
    is_active: bool
    logo_url: str | None = None
    login_max_attempts: int
    login_lockout_minutes: int


class SchoolCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    code: str = Field(min_length=1, max_length=50, pattern=r"^[a-z0-9_-]+$")
    board: str = Field(default="CBSE", max_length=50)
    owner_email: EmailStr
    # Optional; derived from the owner's email when omitted. Immutable once created.
    owner_username: Annotated[str, StringConstraints(max_length=254)] | None = None
    owner_full_name: str = Field(min_length=1, max_length=200)
    # Policy is checked by the router once the owner's username is known.
    owner_password: str = Field(max_length=128)

    @field_validator("owner_username")
    @classmethod
    def _owner_username(cls, v: str | None) -> str | None:
        if v is None or not v.strip():
            return None
        return normalize_username(v)


def _not_null(v: object) -> object:
    if v is None:
        raise ValueError("must not be null")
    return v


class SchoolOwnerUpdate(BaseModel):
    """What a school owner may change on their own school (never is_active)."""

    model_config = ConfigDict(extra="forbid")

    name: _Name | None = None
    board: _Board | None = None
    # Sign-in lockout: failed attempts allowed before a lock, and how long the lock lasts.
    login_max_attempts: int | None = Field(default=None, ge=3, le=10)
    login_lockout_minutes: int | None = Field(default=None, ge=5, le=1440)

    _no_null = field_validator(
        "name", "board", "login_max_attempts", "login_lockout_minutes"
    )(_not_null)


class SchoolUpdate(SchoolOwnerUpdate):
    model_config = ConfigDict(extra="ignore")

    is_active: bool | None = None

    _no_null_active = field_validator("is_active")(_not_null)
