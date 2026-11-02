from typing import Any, Literal

from pydantic import BaseModel

from app.core.schema_types import UtcDateTime

Level = Literal["platform", "school", "branch", "user"]
IntegrationName = Literal["sms", "whatsapp", "smtp", "razorpay", "storage"]


class SettingItem(BaseModel):
    key: str
    group: str
    label: str
    help: str
    type: str
    choices: list[str]
    min: int | None
    max: int | None
    secret: bool
    # Effective value; always null for secrets (only `is_set` is returned).
    value: Any
    # True when a value is stored at this level (for secrets: a secret is saved).
    is_set: bool
    # Where `value` comes from: own, branch, school, platform, env or default.
    source: str
    default: Any
    can_edit: bool
    updated_by_name: str | None
    updated_at: UtcDateTime | None


class SettingWrite(BaseModel):
    # null or an empty string resets the setting to its default (a secret: clears it).
    value: Any = None
    school_id: int | None = None
    branch_id: int | None = None


class LevelInfo(BaseModel):
    level: Level
    can_edit: bool
    # "school" or "branch" when the caller (a platform admin or school owner) must pass that id.
    requires: Literal["school", "branch"] | None


class LevelsOut(BaseModel):
    levels: list[LevelInfo]
    features: dict[str, bool]


class IntegrationTestResult(BaseModel):
    ok: bool
    detail: str
