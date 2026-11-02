"""Audit trail: `record` writes, the viewer functions read. Nothing here updates or deletes."""

import csv
import io
import logging
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from typing import Any

from fastapi import Request, status
from sqlalchemy import false, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import request_context
from app.core.errors import ApiError
from app.core.rate_limit import client_ip
from app.core.schema_types import utc_iso
from app.core.tenant import AnySelect
from app.modules.audit.models import AuditLog
from app.modules.audit.schemas import AuditEntry, AuditPage
from app.modules.users.models import Role, User

logger = logging.getLogger("app.audit")

_UNSET: Any = object()
_MAX_TEXT = 200
EXPORT_LIMIT = 10_000
VIEWER_ROLES = frozenset({Role.SUPER_ADMIN, Role.SCHOOL_OWNER, Role.MANAGEMENT, Role.HEADMASTER})


def _clean(detail: dict[str, Any] | None) -> dict[str, Any] | None:
    if not detail:
        return None
    out: dict[str, Any] = {}
    for key, value in detail.items():
        if isinstance(value, str):
            value = value[:_MAX_TEXT]
        elif not isinstance(value, bool | int | float | type(None)):
            value = str(value)[:_MAX_TEXT]
        out[str(key)[:50]] = value
    return out


async def record(
    db: AsyncSession,
    actor: User | None,
    action: str,
    entity_type: str | None = None,
    entity_id: int | str | None = None,
    outcome: str = "ok",
    detail: dict[str, Any] | None = None,
    request: Request | None = None,
    *,
    school_id: int | None = _UNSET,
    branch_id: int | None = _UNSET,
    commit: bool = False,
) -> None:
    """Add one audit row. It never raises into the caller.

    By default the row joins the caller's open transaction (it is saved by the caller's commit
    and dropped by its rollback). Pass `commit=True` for events that have no business write of
    their own (a failed sign-in, a read, a denied action). School and branch default to the
    actor's; pass them when the event concerns another record's school or branch.
    `detail` is for non-personal facts only (a setting key, a purpose, a count), never values.
    """
    try:
        if request is not None:
            ip: str | None = client_ip(request.scope)
            rid = getattr(request.state, "request_id", None)
        else:
            ip = request_context.request_ip.get()
            rid = request_context.request_id.get()
        row = AuditLog(
            school_id=(actor.school_id if actor else None) if school_id is _UNSET else school_id,
            branch_id=(actor.branch_id if actor else None) if branch_id is _UNSET else branch_id,
            actor_user_id=actor.id if actor else None,
            actor_role=actor.role.value if actor else None,
            action=action[:50],
            entity_type=entity_type,
            entity_id=None if entity_id is None else str(entity_id)[:40],
            outcome=outcome,
            ip=ip,
            request_id=rid,
            detail=_clean(detail),
        )
    except Exception as exc:
        # Type only: the message may carry personal data or SQL parameters.
        logger.error("Audit row not built (%s) for %s", type(exc).__name__, action[:50])
        return

    # The caller's own pending writes are flushed first, outside the savepoint. An error there is
    # the caller's error and propagates; it must not be hidden inside the audit's savepoint, where
    # it would leave the session unusable (the caller's rows lost, PendingRollbackError later).
    await db.flush()
    try:
        # The savepoint holds the audit row only. If its insert fails, only the savepoint is rolled
        # back and the caller's transaction carries on without the audit row.
        async with db.begin_nested():
            db.add(row)
            await db.flush()
    except Exception as exc:
        # Type only: the message may carry SQL parameters.
        logger.error("Audit write failed (%s) for %s", type(exc).__name__, action[:50])
        return
    if commit:
        await db.commit()


# ------------------------------------------------------------------ viewer


@dataclass(frozen=True)
class AuditFilters:
    date_from: date | None = None
    date_to: date | None = None
    action: str | None = None
    actor_id: int | None = None
    entity_type: str | None = None
    school_id: int | None = None  # platform admin only


def _scoped(stmt: AnySelect, actor: User, f: AuditFilters) -> AnySelect:
    if actor.role not in VIEWER_ROLES:
        raise ApiError(status.HTTP_403_FORBIDDEN, "Not allowed", "forbidden")
    if actor.role == Role.SUPER_ADMIN:
        if f.school_id is not None:
            stmt = stmt.where(AuditLog.school_id == f.school_id)
    else:
        if actor.school_id is None:
            return stmt.where(false())
        stmt = stmt.where(AuditLog.school_id == actor.school_id)
        if actor.role != Role.SCHOOL_OWNER:
            if actor.branch_id is None:
                return stmt.where(false())
            stmt = stmt.where(AuditLog.branch_id == actor.branch_id)
    if f.date_from is not None:
        stmt = stmt.where(AuditLog.at >= datetime.combine(f.date_from, time.min, tzinfo=UTC))
    if f.date_to is not None:
        stmt = stmt.where(
            AuditLog.at < datetime.combine(f.date_to + timedelta(days=1), time.min, tzinfo=UTC)
        )
    if f.action:
        if f.action.endswith("*"):
            stmt = stmt.where(AuditLog.action.like(f.action[:-1].replace("%", "") + "%"))
        else:
            stmt = stmt.where(AuditLog.action == f.action)
    if f.actor_id is not None:
        stmt = stmt.where(AuditLog.actor_user_id == f.actor_id)
    if f.entity_type:
        stmt = stmt.where(AuditLog.entity_type == f.entity_type)
    return stmt


def _entry(row: AuditLog, name: str | None) -> AuditEntry:
    return AuditEntry(
        id=row.id,
        at=row.at,
        school_id=row.school_id,
        branch_id=row.branch_id,
        actor_user_id=row.actor_user_id,
        actor_name=name,
        actor_role=row.actor_role,
        action=row.action,
        entity_type=row.entity_type,
        entity_id=row.entity_id,
        outcome=row.outcome,
        ip=row.ip,
        request_id=row.request_id,
        detail=row.detail,
    )


def _with_names() -> Any:
    return select(AuditLog, User.full_name).outerjoin(User, User.id == AuditLog.actor_user_id)


async def list_entries(
    db: AsyncSession, actor: User, f: AuditFilters, page: int, page_size: int
) -> AuditPage:
    total = int(await db.scalar(_scoped(select(func.count(AuditLog.id)), actor, f)) or 0)
    stmt = (
        _scoped(_with_names(), actor, f)
        .order_by(AuditLog.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    rows = (await db.execute(stmt)).all()
    return AuditPage(
        items=[_entry(r, name) for r, name in rows], total=total, page=page, page_size=page_size
    )


def _csv_cell(value: Any) -> str:
    text = "" if value is None else str(value)
    if text and text[0] in ("=", "+", "-", "@", "\t", "\r"):
        return "'" + text
    return text


async def export_csv(db: AsyncSession, actor: User, f: AuditFilters) -> str:
    stmt = _scoped(_with_names(), actor, f).order_by(AuditLog.id.desc()).limit(EXPORT_LIMIT)
    rows = (await db.execute(stmt)).all()
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\r\n")
    writer.writerow(
        [
            "id", "at_utc", "school_id", "branch_id", "actor_user_id", "actor_name",
            "actor_role", "action", "entity_type", "entity_id", "outcome", "ip", "request_id",
            "detail",
        ]
    )
    for r, name in rows:
        writer.writerow(
            _csv_cell(v)
            for v in (
                r.id,
                utc_iso(r.at),
                r.school_id,
                r.branch_id,
                r.actor_user_id,
                name,
                r.actor_role,
                r.action,
                r.entity_type,
                r.entity_id,
                r.outcome,
                r.ip,
                r.request_id,
                "" if r.detail is None else str(r.detail),
            )
        )
    return buf.getvalue()
