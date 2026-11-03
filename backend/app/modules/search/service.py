"""Global search: one query per group, each limited to what the signed-in user may already see.

Every group reuses the module's own scope helper (students, fees, admissions, notices), so the
result can never be wider than the list screen for the same user. Feature switches and the
parents' fee setting remove whole groups. The search text is never logged or stored.
"""

import re
from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.core.tenant import scope_admissions, scope_fees, scope_notices, scope_students
from app.modules.admissions.models import AdmissionApplication
from app.modules.audit import service as audit
from app.modules.fees.models import Invoice, Payment, PaymentStatus
from app.modules.notices import service as notices_service
from app.modules.notices.models import Notice
from app.modules.search.schemas import SearchGroup, SearchItem, SearchResponse, SearchType
from app.modules.settings import service as settings_service
from app.modules.students.models import Guardian, Student
from app.modules.users.models import Role, User

MIN_CHARS = 2
MAX_CHARS = 60
# A query made only of digits and phone punctuation also matches guardians' mobile numbers,
# once it has at least this many digits (shorter digit strings would match far too much).
MIN_PHONE_DIGITS = 4
_PHONE_QUERY = re.compile(r"[+\d\s\-()]+")

_STUDENT_VIEWERS = frozenset(
    {
        Role.SCHOOL_OWNER,
        Role.MANAGEMENT,
        Role.HEADMASTER,
        Role.CLERK,
        Role.TEACHER,
        Role.ACCOUNTANT,
        Role.PARENT,
        Role.STUDENT,
    }
)
_GUARDIAN_VIEWERS = frozenset({Role.SCHOOL_OWNER, Role.MANAGEMENT, Role.HEADMASTER, Role.CLERK})
_ADMISSION_VIEWERS = _GUARDIAN_VIEWERS
_FEE_STAFF = frozenset(
    {Role.SCHOOL_OWNER, Role.MANAGEMENT, Role.HEADMASTER, Role.CLERK, Role.ACCOUNTANT}
)
_FAMILY = frozenset({Role.PARENT, Role.STUDENT})


def _search_text(q: str) -> str:
    term = q.strip()
    if len(term) < MIN_CHARS:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"Enter at least {MIN_CHARS} characters"
        )
    return term[:MAX_CHARS]


def _contains(column: Any, needle: str) -> Any:
    """Case-insensitive substring match; % and _ in the text are matched literally."""
    return func.lower(column).contains(needle, autoescape=True)


def _name_match(first: Any, last: Any, needle: str) -> Any:
    return or_(
        _contains(first, needle),
        _contains(last, needle),
        _contains(first + " " + last, needle),
    )


def _echo(term: str) -> str:
    """The query as echoed back. A phone-like query keeps only its last two digits, so a phone
    number is never repeated in the response."""
    if _phone_digits(term) is None:
        return term
    digit_positions = [i for i, c in enumerate(term) if c.isdigit()]
    keep = set(digit_positions[-2:])
    return "".join(c if not c.isdigit() or i in keep else "*" for i, c in enumerate(term))


def _phone_digits(term: str) -> str | None:
    if not _PHONE_QUERY.fullmatch(term):
        return None
    digits = re.sub(r"\D", "", term)
    return digits if len(digits) >= MIN_PHONE_DIGITS else None


def _fee_scope(stmt: Any, model: Any, user: User) -> Any:
    """Families reach fee records only through their own students; staff through the fee scope."""
    if user.role in _FAMILY:
        return stmt.where(model.student_id.in_(scope_students(select(Student.id), user)))
    return scope_fees(stmt, model, user)


async def _students(db: AsyncSession, user: User, needle: str, limit: int) -> list[SearchItem]:
    stmt = scope_students(select(Student), user).where(
        or_(
            _name_match(Student.first_name, Student.last_name, needle),
            _contains(Student.admission_no, needle),
        )
    )
    rows = await db.scalars(
        stmt.order_by(Student.first_name, Student.last_name, Student.id).limit(limit)
    )
    return [
        SearchItem(
            id=s.id,
            title=f"{s.first_name} {s.last_name}",
            subtitle=s.admission_no,
            url=f"/students/{s.id}",
        )
        for s in rows
    ]


async def _guardians(
    db: AsyncSession, user: User, needle: str, digits: str | None, limit: int
) -> list[SearchItem]:
    cond = _contains(Guardian.full_name, needle)
    if digits is not None:
        cond = or_(cond, Guardian.phone.contains(digits, autoescape=True))
    stmt = (
        scope_students(
            select(Guardian, Student).join(Student, Student.id == Guardian.student_id), user
        )
        .where(cond)
        .order_by(Guardian.full_name, Guardian.id)
        .limit(limit)
    )
    rows = (await db.execute(stmt)).all()
    if digits is not None and rows:
        # Finding someone by their phone number is recorded (counts only, never the number).
        await audit.record(
            db, user, "guardian.searched", "guardian", None,
            detail={"matched_by": "phone", "rows": len(rows)}, commit=True,
        )
    return [
        SearchItem(
            id=g.id,
            title=g.full_name,
            subtitle=f"{g.relation.value} of {s.first_name} {s.last_name}",
            url=f"/students/{s.id}",
        )
        for g, s in rows
    ]


async def _admissions(db: AsyncSession, user: User, needle: str, limit: int) -> list[SearchItem]:
    stmt = scope_admissions(select(AdmissionApplication), user).where(
        or_(
            _name_match(AdmissionApplication.first_name, AdmissionApplication.last_name, needle),
            _contains(AdmissionApplication.guardian_name, needle),
        )
    )
    rows = await db.scalars(
        stmt.order_by(
            AdmissionApplication.first_name, AdmissionApplication.last_name, AdmissionApplication.id
        ).limit(limit)
    )
    return [
        SearchItem(
            id=a.id,
            title=f"{a.first_name} {a.last_name}",
            subtitle=a.status.value,
            url=f"/admissions/{a.id}",
        )
        for a in rows
    ]


async def _invoices(db: AsyncSession, user: User, needle: str, limit: int) -> list[SearchItem]:
    name = aliased(Student)
    stmt = _fee_scope(
        select(Invoice, name).join(name, name.id == Invoice.student_id), Invoice, user
    ).where(_contains(Invoice.invoice_no, needle))
    if user.role in _FAMILY:
        stmt = stmt.where(Invoice.status_cancelled.is_(False))
    rows = (await db.execute(stmt.order_by(Invoice.id.desc()).limit(limit))).all()
    return [
        SearchItem(
            id=inv.id,
            title=inv.invoice_no,
            subtitle=f"{s.first_name} {s.last_name}",
            url=f"/students/{s.id}",
        )
        for inv, s in rows
    ]


async def _receipts(db: AsyncSession, user: User, needle: str, limit: int) -> list[SearchItem]:
    name = aliased(Student)
    stmt = _fee_scope(
        select(Payment, name).join(name, name.id == Payment.student_id), Payment, user
    ).where(_contains(Payment.receipt_no, needle))
    if user.role in _FAMILY:
        stmt = stmt.where(Payment.status == PaymentStatus.RECEIVED)
    rows = (await db.execute(stmt.order_by(Payment.id.desc()).limit(limit))).all()
    return [
        SearchItem(
            id=p.id,
            title=p.receipt_no,
            subtitle=f"{s.first_name} {s.last_name}",
            url=f"/students/{s.id}",
        )
        for p, s in rows
    ]


async def _notices(db: AsyncSession, user: User, needle: str, limit: int) -> list[SearchItem]:
    stmt = scope_notices(select(Notice), user, notices_service.today()).where(
        _contains(Notice.title, needle)
    )
    rows = await db.scalars(stmt.order_by(Notice.created_at.desc(), Notice.id.desc()).limit(limit))
    return [
        SearchItem(id=n.id, title=n.title, subtitle=n.category.value, url="/notices")
        for n in rows
    ]


async def search(db: AsyncSession, user: User, q: str, limit: int) -> SearchResponse:
    term = _search_text(q)
    needle = term.lower()
    if user.role == Role.SUPER_ADMIN or user.school_id is None:
        # Platform admins have no school of their own to search in.
        return SearchResponse(q=_echo(term), groups=[])
    features = await settings_service.school_features(db, user.school_id)
    family = user.role in _FAMILY
    fees_for_user = user.role in _FEE_STAFF or (
        family
        and await settings_service.get_bool(
            db, "portal.parent_sees_fees", school_id=user.school_id
        )
    )
    digits = _phone_digits(term)

    # (type, allowed for this user, loader). Groups come out in this order.
    plan: list[tuple[SearchType, bool, Callable[[], Awaitable[list[SearchItem]]]]] = [
        (
            "students",
            features["students"] and user.role in _STUDENT_VIEWERS,
            lambda: _students(db, user, needle, limit),
        ),
        (
            "guardians",
            features["students"] and user.role in _GUARDIAN_VIEWERS,
            lambda: _guardians(db, user, needle, digits, limit),
        ),
        (
            "admissions",
            features["admissions"] and user.role in _ADMISSION_VIEWERS,
            lambda: _admissions(db, user, needle, limit),
        ),
        (
            "invoices",
            features["fees"] and fees_for_user,
            lambda: _invoices(db, user, needle, limit),
        ),
        (
            "receipts",
            features["fees"] and fees_for_user,
            lambda: _receipts(db, user, needle, limit),
        ),
        ("notices", features["notices"], lambda: _notices(db, user, needle, limit)),
    ]
    groups: list[SearchGroup] = []
    for kind, allowed, loader in plan:
        if not allowed:
            continue
        items = await loader()
        if items:
            groups.append(SearchGroup(type=kind, items=items))
    return SearchResponse(q=_echo(term), groups=groups)
