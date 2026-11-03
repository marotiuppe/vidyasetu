"""Discounts applied when invoices are generated: student concessions and sibling discounts.

Discounts are fixed at generation time and stored on the invoice, so changing or deactivating a
concession later never changes an invoice that already exists.
"""

from collections import defaultdict
from collections.abc import Collection
from dataclasses import dataclass
from datetime import date

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.fees.models import ConcessionKind, FeeConcession
from app.modules.students.models import Enrollment, Guardian, Student, StudentStatus

BASIS_POINTS = 10_000
SIBLING_REASON = "Sibling discount"
REASON_MAX = 200


@dataclass(frozen=True)
class ActiveConcession:
    name: str
    kind: ConcessionKind
    value: int
    fee_head_id: int | None


async def load_concessions(
    db: AsyncSession, school_id: int, year_id: int, student_ids: Collection[int]
) -> dict[int, list[ActiveConcession]]:
    """Active concessions of the year for the given students, oldest first."""
    ids = list(student_ids)
    if not ids:
        return {}
    rows = await db.execute(
        select(FeeConcession)
        .where(
            FeeConcession.school_id == school_id,
            FeeConcession.academic_year_id == year_id,
            FeeConcession.student_id.in_(ids),
            FeeConcession.active.is_(True),
        )
        .order_by(FeeConcession.id)
    )
    out: dict[int, list[ActiveConcession]] = defaultdict(list)
    for c in rows.scalars():
        out[c.student_id].append(
            ActiveConcession(
                name=c.name, kind=c.kind, value=c.value, fee_head_id=c.fee_head_id
            )
        )
    return dict(out)


async def sibling_positions(
    db: AsyncSession, school_id: int, year_id: int, student_ids: Collection[int]
) -> dict[int, int]:
    """1-based birth-order-like position of each student among the active, enrolled children of
    the same parent login (ordered by admission date, then id).

    A student linked to several parent logins gets the highest position found, so the family
    that has the most children decides. Students without a parent login are not in the result.
    """
    ids = list(student_ids)
    if not ids:
        return {}
    links = await db.execute(
        select(Guardian.student_id, Guardian.user_id).where(
            Guardian.school_id == school_id,
            Guardian.student_id.in_(ids),
            Guardian.user_id.is_not(None),
        )
    )
    logins_of: dict[int, set[int]] = defaultdict(set)
    for student_id, user_id in links.all():
        if user_id is not None:
            logins_of[student_id].add(int(user_id))
    if not logins_of:
        return {}
    login_ids = {u for logins in logins_of.values() for u in logins}
    siblings = await db.execute(
        select(Guardian.user_id, Student.id, Student.admission_date)
        .join(Student, Student.id == Guardian.student_id)
        .join(
            Enrollment,
            and_(
                Enrollment.student_id == Student.id,
                Enrollment.academic_year_id == year_id,
            ),
        )
        .where(
            Guardian.school_id == school_id,
            Guardian.user_id.in_(login_ids),
            Student.school_id == school_id,
            Student.status == StudentStatus.ACTIVE,
        )
        .distinct()
    )
    by_login: dict[int, list[tuple[date, int]]] = defaultdict(list)
    for user_id, student_id, admitted in siblings.all():
        if user_id is not None:
            by_login[int(user_id)].append((admitted, int(student_id)))

    position: dict[tuple[int, int], int] = {}
    for user_id, members in by_login.items():
        for index, (_, student_id) in enumerate(sorted(members), start=1):
            position[(user_id, student_id)] = index

    out: dict[int, int] = {}
    for student_id, logins in logins_of.items():
        found = [position[(u, student_id)] for u in logins if (u, student_id) in position]
        if found:
            out[student_id] = max(found)
    return out


def compute_discount(
    items: list[tuple[int, int, str]],
    concessions: list[ActiveConcession],
    sibling_percent: int,
    sibling_from_child: int,
    sibling_position: int | None,
) -> tuple[int, str | None]:
    """Total discount in paise and the reason text for one invoice.

    `items` are (fee head id, amount, name) of the generated lines. A percent concession is taken
    from the lines of its head (or the whole gross when it has no head); a fixed one is capped at
    that same base. The sibling discount is a percentage of the gross. The total never exceeds
    the gross.
    """
    gross = sum(amount for _, amount, _ in items)
    total = 0
    names: list[str] = []
    for c in concessions:
        if c.fee_head_id is None:
            base = gross
        else:
            base = sum(amount for head, amount, _ in items if head == c.fee_head_id)
        if base <= 0:
            continue
        if c.kind == ConcessionKind.PERCENT:
            amount_off = base * c.value // BASIS_POINTS
        else:
            amount_off = min(c.value, base)
        if amount_off > 0:
            total += amount_off
            names.append(c.name)
    if (
        sibling_percent > 0
        and sibling_position is not None
        and sibling_position >= sibling_from_child
        and gross > 0
    ):
        sibling_off = gross * sibling_percent // 100
        if sibling_off > 0:
            total += sibling_off
            names.append(SIBLING_REASON)
    total = min(total, gross)
    if total <= 0:
        return 0, None
    return total, ", ".join(names)[:REASON_MAX]
