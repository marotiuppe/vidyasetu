"""Policy acceptance (per user) and parental consent (per student).

Consent rows are only ever added; the latest row per student and purpose is the current state.
"""

from fastapi import status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import request_context
from app.core.errors import ApiError
from app.core.tenant import scope_students
from app.db.base import utcnow
from app.modules.audit import service as audit
from app.modules.consent.models import (
    ConsentMethod,
    GuardianConsent,
    Policy,
    PolicyAcceptance,
    Purpose,
)
from app.modules.consent.schemas import (
    ConsentCreate,
    ConsentCurrent,
    ConsentEntry,
    ConsentsOut,
    PoliciesOut,
    PolicyAccept,
    PolicyState,
)
from app.modules.settings import service as settings_service
from app.modules.students.models import Student
from app.modules.users.models import Role, User

# Staff who may record a paper or in-person decision (the same roles that edit students).
RECORDERS = frozenset(
    {Role.SCHOOL_OWNER, Role.MANAGEMENT, Role.HEADMASTER, Role.CLERK}
)
_STAFF_METHODS = (ConsentMethod.PAPER, ConsentMethod.IN_PERSON)


def _err(status_code: int, detail: str, code: str) -> ApiError:
    return ApiError(status_code, detail, code)


# ----------------------------------------------------------------- policies


async def policies_for(db: AsyncSession, user: User) -> PoliciesOut:
    versions = await settings_service.policy_versions(db)
    accepted = {
        (a.policy.value, a.version): a.accepted_at
        for a in await db.scalars(
            select(PolicyAcceptance).where(PolicyAcceptance.user_id == user.id)
        )
    }
    states = [
        PolicyState(
            policy=policy,
            version=versions[policy.value],
            accepted=(policy.value, versions[policy.value]) in accepted,
            accepted_at=accepted.get((policy.value, versions[policy.value])),
        )
        for policy in Policy
    ]
    return PoliciesOut(policies=states, pending=any(not s.accepted for s in states))


async def accept_policy(db: AsyncSession, user: User, data: PolicyAccept) -> PoliciesOut:
    versions = await settings_service.policy_versions(db)
    if data.version != versions[data.policy.value]:
        raise _err(
            status.HTTP_409_CONFLICT, "This is not the current version", "version_mismatch"
        )
    exists = await db.scalar(
        select(PolicyAcceptance.id).where(
            PolicyAcceptance.user_id == user.id,
            PolicyAcceptance.policy == data.policy,
            PolicyAcceptance.version == data.version,
        )
    )
    if exists is None:
        db.add(
            PolicyAcceptance(
                user_id=user.id,
                policy=data.policy,
                version=data.version,
                accepted_at=utcnow(),
                ip=request_context.request_ip.get(),
            )
        )
        await audit.record(
            db, user, "consent.recorded", "policy", data.policy.value,
            detail={"policy": data.policy.value, "version": data.version},
        )
        await db.commit()
    return await policies_for(db, user)


# --------------------------------------------------------- parental consent


async def _student(db: AsyncSession, actor: User, student_id: int) -> Student:
    student: Student | None = await db.scalar(
        scope_students(select(Student), actor).where(Student.id == student_id)
    )
    if student is None:
        raise _err(status.HTTP_404_NOT_FOUND, "Student not found", "not_found")
    return student


async def current_status(db: AsyncSession, student_id: int) -> dict[str, str]:
    """Current decision per purpose (`none` when nothing is recorded)."""
    rows = await db.scalars(
        select(GuardianConsent)
        .where(GuardianConsent.student_id == student_id)
        .order_by(GuardianConsent.id)
    )
    out = {p.value: "none" for p in Purpose}
    for row in rows:
        out[row.purpose.value] = row.status.value
    return out


async def get_consents(db: AsyncSession, actor: User, student_id: int) -> ConsentsOut:
    student = await _student(db, actor, student_id)
    rows = (
        await db.execute(
            select(GuardianConsent, User.full_name)
            .join(User, User.id == GuardianConsent.recorded_by_user_id)
            .where(GuardianConsent.student_id == student.id)
            .order_by(GuardianConsent.id.desc())
        )
    ).all()
    latest: dict[Purpose, GuardianConsent] = {}
    for row, _ in reversed(rows):
        latest[row.purpose] = row
    current = [
        ConsentCurrent(
            purpose=p,
            status=latest[p].status if p in latest else "none",
            method=latest[p].method if p in latest else None,
            recorded_at=latest[p].recorded_at if p in latest else None,
        )
        for p in Purpose
    ]
    history = [
        ConsentEntry(
            id=r.id,
            purpose=r.purpose,
            status=r.status,
            method=r.method,
            note=r.note,
            given_by_user_id=r.given_by_user_id,
            recorded_by_user_id=r.recorded_by_user_id,
            recorded_by_name=name,
            recorded_at=r.recorded_at,
        )
        for r, name in rows
    ]
    return ConsentsOut(student_id=student.id, current=current, history=history)


async def record_consent(
    db: AsyncSession, actor: User, student_id: int, data: ConsentCreate
) -> ConsentsOut:
    if actor.role != Role.PARENT and actor.role not in RECORDERS:
        raise _err(status.HTTP_403_FORBIDDEN, "Not allowed", "forbidden")
    student = await _student(db, actor, student_id)  # 404 when out of scope
    if actor.role == Role.PARENT:
        if data.method not in (None, ConsentMethod.ONLINE):
            raise _err(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                "Parents record consent online",
                "invalid_method",
            )
        method = ConsentMethod.ONLINE
        given_by: int | None = actor.id
    else:
        method = data.method or ConsentMethod.PAPER
        if method not in _STAFF_METHODS:
            raise _err(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                "Staff record paper or in-person consent",
                "invalid_method",
            )
        given_by = None
    db.add(
        GuardianConsent(
            school_id=student.school_id,
            branch_id=student.branch_id,
            student_id=student.id,
            purpose=data.purpose,
            status=data.status,
            given_by_user_id=given_by,
            recorded_by_user_id=actor.id,
            method=method,
            note=data.note or None,
            recorded_at=utcnow(),
        )
    )
    await db.flush()
    await audit.record(
        db, actor, "consent.recorded", "student", student.id,
        detail={"purpose": data.purpose.value, "status": data.status.value, "method": method.value},
        school_id=student.school_id, branch_id=student.branch_id,
    )
    await db.commit()
    return await get_consents(db, actor, student.id)

