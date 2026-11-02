from datetime import datetime
from typing import Any

from pydantic import BaseModel


class AuditEntry(BaseModel):
    id: int
    at: datetime
    school_id: int | None
    branch_id: int | None
    actor_user_id: int | None
    actor_name: str | None
    actor_role: str | None
    action: str
    entity_type: str | None
    entity_id: str | None
    outcome: str
    ip: str | None
    request_id: str | None
    detail: dict[str, Any] | None


class AuditPage(BaseModel):
    items: list[AuditEntry]
    total: int
    page: int
    page_size: int
