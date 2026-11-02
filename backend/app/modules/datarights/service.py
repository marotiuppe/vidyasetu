"""Data-rights requests: access, correction and erasure.

This is a workflow record only. An erasure request asks the school to decide; nothing is deleted
here. Handlers are the school owner and the management or headmaster of the student's branch.
"""

from datetime import timedelta
from typing import Any

from fastapi import status
from sqlalchemy import false, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.core.errors import ApiError
from app.core.tenant import AnySelect, scope_students
from app.db.base import utcnow
from app.modules.audit import service as audit
from app.modules.datarights.models import DataRequest, RequestStatus
from app.modules.datarights.schemas import (
    DataRequestCreate,
    DataRequestOut,
    DataRequestPage,
    DataRequestUpdate,
)
from app.modules.settings import service as settings_service
from app.modules.students.models import Student
from app.modules.users.models import Role, User

HANDLER_ROLES = frozenset(
    {Role.SUPER_ADMIN, Role.SCHOOL_OWNER, Role.MANAGEMENT, Role.HEADMASTER}
)
_CLOSED = (RequestStatus.COMPLETED, RequestStatus.REJECTED)
# Allowed moves; a closed request stays closed.
_NEXT = {
    RequestStatus.OPEN: {
        RequestStatus.IN_PROGRESS,
        RequestStatus.COMPLETED,
        RequestStatus.REJECTED,
    },
    RequestStatus.IN_PROGRESS: {RequestStatus.COMPLETED, RequestStatus.REJECTED},
}


def _err(status_code: int, detail: str, code: str) -> ApiError:
    return ApiError(status_code, detail, code)


def _query() -> Any:
    requester = aliased(User)
    return (
        select(
            DataRequest,
            requester.full_name,
            requester.role,
            Student.first_name,
            Student.last_name,
        )
        .join(requester, requester.id == DataRequest.requester_user_id)
        .outerjoin(Student, Student.id == DataRequest.student_id)
    )


def _out(row: Any) -> DataRequestOut:
    req, requester_name, requester_role, first, last = row
    today = utcnow().date()
    return DataRequestOut(
        id=req.id,
        type=req.type,
        status=req.status,
        message=req.message,
        response_note=req.response_note,
        student_id=req.student_id,
        student_name=f"{first} {last}" if first is not None else None,
        requester_user_id=req.requester_user_id,
        requester_name=requester_name,
        requester_role=requester_role.value if requester_role is not None else None,
        handled_by_user_id=req.handled_by_user_id,
        created_at=req.created_at,
        updated_at=req.updated_at,
        due_on=req.due_on,
        overdue=req.status not in _CLOSED and req.due_on < today,
    )


def _handler_scope(stmt: AnySelect, actor: User) -> AnySelect:
    if actor.role not in HANDLER_ROLES:
        raise _err(status.HTTP_403_FORBIDDEN, "Not allowed", "forbidden")
    if actor.role == Role.SUPER_ADMIN:
        return stmt
    if actor.school_id is None:
        return stmt.where(false())
    stmt = stmt.where(DataRequest.school_id == actor.school_id)
    if actor.role == Role.SCHOOL_OWNER:
        return stmt
    if actor.branch_id is None:
        return stmt.where(false())
    return stmt.where(DataRequest.branch_id == actor.branch_id)


async def create_request(db: AsyncSession, actor: User, data: DataRequestCreate) -> DataRequestOut:
    student: Student | None = None
    if data.student_id is not None:
        if actor.role not in (Role.PARENT, Role.STUDENT):
            raise _err(
                status.HTTP_403_FORBIDDEN,
                "You can only make a request about your own data",
                "forbidden",
            )
        student = await db.scalar(
            scope_students(select(Student), actor).where(Student.id == data.student_id)
        )
        if student is None:
            raise _err(status.HTTP_404_NOT_FOUND, "Student not found", "not_found")
    days = (
        int(await settings_service.resolve(db, "legal.grievance_response_days", user=actor))
        if actor.school_id is not None
        else 15
    )
    now = utcnow()
    req = DataRequest(
        school_id=actor.school_id,
        branch_id=student.branch_id if student is not None else actor.branch_id,
        requester_user_id=actor.id,
        student_id=student.id if student is not None else None,
        type=data.type,
        message=data.message,
        status=RequestStatus.OPEN,
        created_at=now,
        updated_at=now,
        due_on=(now + timedelta(days=days)).date(),
    )
    db.add(req)
    await db.flush()
    await audit.record(
        db, actor, "data_request.created", "data_request", req.id,
        detail={"type": req.type.value, "for_child": student is not None},
        school_id=req.school_id, branch_id=req.branch_id,
    )
    await db.commit()
    return await _get_out(db, req.id)


async def _get_out(db: AsyncSession, request_id: int) -> DataRequestOut:
    row = (await db.execute(_query().where(DataRequest.id == request_id))).one()
    return _out(row)


async def _page(
    db: AsyncSession, stmt: AnySelect, count_stmt: AnySelect, page: int, page_size: int
) -> DataRequestPage:
    total = int(await db.scalar(count_stmt) or 0)
    rows = (
        await db.execute(
            stmt.order_by(DataRequest.id.desc()).offset((page - 1) * page_size).limit(page_size)
        )
    ).all()
    return DataRequestPage(
        items=[_out(r) for r in rows], total=total, page=page, page_size=page_size
    )


async def list_mine(
    db: AsyncSession, actor: User, page: int, page_size: int
) -> DataRequestPage:
    where = DataRequest.requester_user_id == actor.id
    return await _page(
        db,
        _query().where(where),
        select(func.count(DataRequest.id)).where(where),
        page,
        page_size,
    )


async def list_requests(
    db: AsyncSession,
    actor: User,
    request_status: RequestStatus | None,
    page: int,
    page_size: int,
) -> DataRequestPage:
    stmt = _handler_scope(_query(), actor)
    count_stmt = _handler_scope(select(func.count(DataRequest.id)), actor)
    if request_status is not None:
        stmt = stmt.where(DataRequest.status == request_status)
        count_stmt = count_stmt.where(DataRequest.status == request_status)
    return await _page(db, stmt, count_stmt, page, page_size)


async def update_request(
    db: AsyncSession, actor: User, request_id: int, data: DataRequestUpdate
) -> DataRequestOut:
    req = await db.scalar(
        _handler_scope(select(DataRequest), actor).where(DataRequest.id == request_id)
    )
    if req is None:
        raise _err(status.HTTP_404_NOT_FOUND, "Request not found", "not_found")
    if data.status not in _NEXT.get(req.status, set()):
        raise _err(
            status.HTTP_409_CONFLICT,
            "This request cannot move to that status",
            "invalid_transition",
        )
    note = data.response_note or None
    if data.status in _CLOSED and not (note or req.response_note):
        raise _err(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Add a response note before closing the request",
            "response_required",
        )
    before = req.status
    req.status = data.status
    if note is not None:
        req.response_note = note
    req.handled_by_user_id = actor.id
    await audit.record(
        db, actor, "data_request.updated", "data_request", req.id,
        detail={"from": before.value, "to": data.status.value, "type": req.type.value},
        school_id=req.school_id, branch_id=req.branch_id,
    )
    await db.commit()
    return await _get_out(db, req.id)
