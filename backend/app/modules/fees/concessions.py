"""Concessions and scholarships: list, create and change. Applied only at invoice generation."""

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.tenant import scope_fees, scope_students
from app.modules.audit import service as audit
from app.modules.fees.models import ConcessionKind, FeeConcession, FeeHead
from app.modules.fees.service import (
    _conflict,
    _get_year,
    _not_found,
    _school_id,
    _unprocessable,
)
from app.modules.fees.tools_schemas import (
    ConcessionCreate,
    ConcessionOut,
    ConcessionPage,
    ConcessionUpdate,
)
from app.modules.students.models import Student
from app.modules.users.models import User

_BASIS_POINTS_MAX = 10_000
_DUPLICATE = "A concession with this name already exists for the student and year"


def _out(c: FeeConcession, student: Student, head_name: str | None) -> ConcessionOut:
    return ConcessionOut(
        id=c.id,
        student_id=c.student_id,
        student_name=f"{student.first_name} {student.last_name}".strip(),
        admission_no=student.admission_no,
        academic_year_id=c.academic_year_id,
        name=c.name,
        kind=c.kind,
        value=c.value,
        fee_head_id=c.fee_head_id,
        fee_head_name=head_name,
        reason=c.reason,
        active=c.active,
        created_at=c.created_at,
    )


def _joined(actor: User, conditions: list[Any]) -> Any:
    """Concessions with their student and head name, scoped to the actor."""
    stmt = (
        select(FeeConcession, Student, FeeHead.name)
        .join(Student, Student.id == FeeConcession.student_id)
        .outerjoin(FeeHead, FeeHead.id == FeeConcession.fee_head_id)
    )
    return scope_fees(stmt, FeeConcession, actor).where(*conditions)


async def _one(db: AsyncSession, actor: User, concession_id: int) -> ConcessionOut:
    row = (await db.execute(_joined(actor, [FeeConcession.id == concession_id]))).first()
    if row is None:
        raise _not_found("Concession")
    return _out(row[0], row[1], row[2])


async def list_concessions(
    db: AsyncSession,
    actor: User,
    student_id: int | None,
    academic_year_id: int | None,
    page: int,
    page_size: int,
) -> ConcessionPage:
    conditions: list[Any] = []
    if student_id is not None:
        conditions.append(FeeConcession.student_id == student_id)
    if academic_year_id is not None:
        conditions.append(FeeConcession.academic_year_id == academic_year_id)
    count_stmt = scope_fees(
        select(func.count()).select_from(FeeConcession), FeeConcession, actor
    ).where(*conditions)
    total = int(await db.scalar(count_stmt) or 0)
    stmt = (
        _joined(actor, conditions)
        .order_by(Student.last_name, Student.first_name, FeeConcession.id)
        .limit(page_size)
        .offset((page - 1) * page_size)
    )
    rows = (await db.execute(stmt)).all()
    return ConcessionPage(
        items=[_out(r[0], r[1], r[2]) for r in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


async def create_concession(
    db: AsyncSession, actor: User, data: ConcessionCreate
) -> ConcessionOut:
    school_id = _school_id(actor)
    year = await _get_year(db, actor, data.academic_year_id)
    student = await db.scalar(
        scope_students(select(Student), actor).where(Student.id == data.student_id)
    )
    if student is None:
        raise _not_found("Student")
    if data.fee_head_id is not None:
        head = await db.scalar(
            scope_fees(select(FeeHead.id), FeeHead, actor).where(FeeHead.id == data.fee_head_id)
        )
        if head is None:
            raise _unprocessable("Unknown fee head")
    concession = FeeConcession(
        school_id=school_id,
        branch_id=student.branch_id,
        student_id=student.id,
        academic_year_id=year.id,
        name=data.name,
        kind=data.kind,
        value=data.value,
        fee_head_id=data.fee_head_id,
        reason=data.reason or None,
        active=True,
        created_by=actor.id,
    )
    db.add(concession)
    try:
        await db.flush()
        await audit.record(
            db, actor, "fee.concession_created", "fee_concession", concession.id,
            detail={"kind": str(data.kind), "whole_invoice": data.fee_head_id is None},
            school_id=school_id, branch_id=student.branch_id,
        )
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise _conflict(_DUPLICATE) from None
    return await _one(db, actor, concession.id)


async def update_concession(
    db: AsyncSession, actor: User, concession_id: int, data: ConcessionUpdate
) -> ConcessionOut:
    """Changes apply to invoices generated from now on. Existing invoices keep their discount."""
    concession: FeeConcession | None = await db.scalar(
        scope_fees(select(FeeConcession), FeeConcession, actor).where(
            FeeConcession.id == concession_id
        )
    )
    if concession is None:
        raise _not_found("Concession")
    if data.value is not None:
        if concession.kind == ConcessionKind.PERCENT and data.value > _BASIS_POINTS_MAX:
            raise _unprocessable("A percent concession cannot exceed 100%")
        concession.value = data.value
    if data.name is not None:
        concession.name = data.name
    if "reason" in data.model_fields_set:
        concession.reason = data.reason or None
    if data.active is not None:
        concession.active = data.active
    try:
        await audit.record(
            db, actor, "fee.concession_updated", "fee_concession", concession.id,
            detail={"fields": ",".join(sorted(data.model_fields_set))},
            school_id=concession.school_id, branch_id=concession.branch_id,
        )
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise _conflict(_DUPLICATE) from None
    return await _one(db, actor, concession.id)
