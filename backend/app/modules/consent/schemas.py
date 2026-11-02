from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, StringConstraints

from app.modules.consent.models import ConsentMethod, ConsentStatus, Policy, Purpose


class PolicyState(BaseModel):
    policy: Policy
    version: str
    accepted: bool
    accepted_at: datetime | None


class PoliciesOut(BaseModel):
    policies: list[PolicyState]
    pending: bool


class PolicyAccept(BaseModel):
    policy: Policy
    version: Annotated[str, StringConstraints(min_length=1, max_length=20)]


class ConsentCurrent(BaseModel):
    purpose: Purpose
    # `none` until a decision has been recorded for this purpose.
    status: ConsentStatus | Literal["none"]
    method: ConsentMethod | None
    recorded_at: datetime | None


class ConsentEntry(BaseModel):
    id: int
    purpose: Purpose
    status: ConsentStatus
    method: ConsentMethod
    note: str | None
    given_by_user_id: int | None
    recorded_by_user_id: int
    recorded_by_name: str | None
    recorded_at: datetime


class ConsentsOut(BaseModel):
    student_id: int
    current: list[ConsentCurrent]
    history: list[ConsentEntry]


class ConsentCreate(BaseModel):
    purpose: Purpose
    status: ConsentStatus
    method: ConsentMethod | None = None
    # Short and non-personal, for example a form number. Never a name or phone number.
    note: Annotated[str, StringConstraints(strip_whitespace=True, max_length=200)] | None = None
