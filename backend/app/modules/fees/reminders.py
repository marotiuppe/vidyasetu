"""Fee reminders: families with dues, a record of each reminder, and a CSV export.

Nothing is sent from here. The channel is "manual" (the office copies the text and tells the
family); SMS and WhatsApp come with the messaging adapters. Guardian phone numbers appear only in
the list and the export, which are limited to roles that already see dues.
"""

import csv
import io
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from sqlalchemy import DateTime, and_, case, false, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import Select

from app.core.schema_types import utc_iso
from app.core.tenant import scope_fees, scope_students
from app.db.base import utcnow
from app.modules.academics.models import SchoolClass
from app.modules.audit import service as audit
from app.modules.fees.models import FeeReminder, Invoice
from app.modules.fees.service import (
    _csv_cell,
    _current_year_id,
    _get_class,
    _get_year,
    _Money,
    _school_id,
    _to_date,
    today,
)
from app.modules.fees.tools_schemas import ReminderMarked, ReminderPage, ReminderRow
from app.modules.students.models import Enrollment, Guardian, Student
from app.modules.users.models import User

MAX_MARK = 200
REMINDER_CHANNEL = "manual"
REMINDER_COLUMNS = [
    "student_id",
    "student_name",
    "admission_no",
    "class_name",
    "guardian_name",
    "guardian_phone",
    "balance_paise",
    "overdue_paise",
    "oldest_due_date",
    "last_reminded_at",
    "reminder_count",
]


@dataclass(frozen=True)
class ReminderFilters:
    academic_year_id: int | None = None
    min_balance_paise: int = 0
    overdue_only: bool = True
    days_before_due: int | None = None
    class_id: int | None = None


async def _due_students(db: AsyncSession, actor: User, f: ReminderFilters) -> Any:
    """Subquery: one row per student whose matching invoices add up to a balance.

    The amounts cover the invoices the filters select. An invoice matches when it has a balance,
    is not cancelled and belongs to the year; `overdue_only` also needs it past due, and
    `days_before_due` needs it due within that many days from today.
    """
    day = today()
    year_id = f.academic_year_id
    if year_id is not None:
        year_id = (await _get_year(db, actor, year_id)).id
    else:
        year_id = await _current_year_id(db, actor)
    m = _Money()
    cond: list[Any] = [Invoice.status_cancelled.is_(False), m.balance > 0]
    if year_id is None:
        cond.append(false())
    else:
        cond.append(Invoice.academic_year_id == year_id)
    if f.overdue_only:
        cond.append(Invoice.due_date < day)
    if f.days_before_due is not None:
        cond.append(Invoice.due_date <= day + timedelta(days=f.days_before_due))
    if f.class_id is not None:
        await _get_class(db, actor, f.class_id)
        cond.append(Enrollment.class_id == f.class_id)
    balance_sum = func.sum(m.balance)
    stmt = (
        m.base(
            Student.id.label("student_id"),
            Student.first_name.label("first_name"),
            Student.last_name.label("last_name"),
            Student.admission_no.label("admission_no"),
            SchoolClass.name.label("class_name"),
            Guardian.full_name.label("guardian_name"),
            Guardian.phone.label("guardian_phone"),
            balance_sum.label("balance"),
            func.sum(case((Invoice.due_date < day, m.balance), else_=0)).label("overdue"),
            func.min(Invoice.due_date).label("oldest"),
        )
        .outerjoin(
            Enrollment,
            and_(Enrollment.student_id == Student.id, Enrollment.academic_year_id == year_id),
        )
        .outerjoin(SchoolClass, SchoolClass.id == Enrollment.class_id)
        .outerjoin(Guardian, and_(Guardian.student_id == Student.id, Guardian.is_primary.is_(True)))
        .where(*cond)
    )
    stmt = scope_fees(stmt, Invoice, actor)
    grouped = stmt.group_by(
        Student.id,
        Student.first_name,
        Student.last_name,
        Student.admission_no,
        SchoolClass.name,
        Guardian.full_name,
        Guardian.phone,
    ).having(balance_sum >= max(1, f.min_balance_paise))
    return grouped.subquery()


def _reminders_sq(actor: User) -> Any:
    """Per student: how many reminders were recorded and when the last one was."""
    return (
        scope_fees(
            select(
                FeeReminder.student_id.label("student_id"),
                func.count().label("cnt"),
                func.max(FeeReminder.created_at, type_=DateTime(timezone=True)).label("last"),
            ),
            FeeReminder,
            actor,
        )
        .group_by(FeeReminder.student_id)
        .subquery()
    )


def _joined(due: Any, rem: Any) -> Select[Any]:
    return (
        select(
            due.c.student_id,
            due.c.first_name,
            due.c.last_name,
            due.c.admission_no,
            due.c.class_name,
            due.c.guardian_name,
            due.c.guardian_phone,
            due.c.balance,
            due.c.overdue,
            due.c.oldest,
            rem.c.last,
            rem.c.cnt,
        )
        .select_from(due)
        .outerjoin(rem, rem.c.student_id == due.c.student_id)
        .order_by(due.c.balance.desc(), due.c.student_id)
    )


def _row(r: Any) -> ReminderRow:
    return ReminderRow(
        student_id=int(r[0]),
        student_name=f"{r[1]} {r[2]}".strip(),
        admission_no=r[3],
        class_name=r[4],
        guardian_name=r[5],
        guardian_phone=r[6],
        balance_paise=int(r[7]),
        overdue_paise=int(r[8]),
        oldest_due_date=_to_date(r[9]),
        last_reminded_at=r[10],
        reminder_count=int(r[11] or 0),
    )


async def list_reminders(
    db: AsyncSession, actor: User, f: ReminderFilters, page: int, page_size: int
) -> ReminderPage:
    due = await _due_students(db, actor, f)
    total = int(await db.scalar(select(func.count()).select_from(due)) or 0)
    rem = _reminders_sq(actor)
    stmt = _joined(due, rem).limit(page_size).offset((page - 1) * page_size)
    rows = (await db.execute(stmt)).all()
    return ReminderPage(
        items=[_row(r) for r in rows], total=total, page=page, page_size=page_size
    )


async def reminders_csv(db: AsyncSession, actor: User, f: ReminderFilters) -> str:
    due = await _due_students(db, actor, f)
    rows = (await db.execute(_joined(due, _reminders_sq(actor)))).all()
    items = [_row(r) for r in rows]
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(REMINDER_COLUMNS)
    for item in items:
        cells: dict[str, Any] = {
            "student_id": item.student_id,
            "student_name": item.student_name,
            "admission_no": item.admission_no,
            "class_name": item.class_name,
            "guardian_name": item.guardian_name,
            "guardian_phone": item.guardian_phone,
            "balance_paise": item.balance_paise,
            "overdue_paise": item.overdue_paise,
            "oldest_due_date": item.oldest_due_date,
            "last_reminded_at": utc_iso(item.last_reminded_at),
            "reminder_count": item.reminder_count,
        }
        writer.writerow(
            ["" if cells[c] is None else _csv_cell(cells[c]) for c in REMINDER_COLUMNS]
        )
    await audit.record(
        db, actor, "fee.reminders_exported", "fee_reminder", None,
        detail={"rows": len(items)}, commit=True,
    )
    return buf.getvalue()


async def mark_reminded(db: AsyncSession, actor: User, student_ids: list[int]) -> ReminderMarked:
    """Record a manual reminder for each student the actor may see. Others are ignored."""
    school_id = _school_id(actor)
    ids = sorted(set(student_ids))[:MAX_MARK]
    allowed = (
        await db.execute(
            scope_students(select(Student.id, Student.branch_id), actor).where(
                Student.id.in_(ids), Student.school_id == school_id
            )
        )
    ).all()
    now = utcnow()
    db.add_all(
        FeeReminder(
            school_id=school_id,
            branch_id=branch_id,
            student_id=student_id,
            invoice_id=None,
            channel=REMINDER_CHANNEL,
            created_by=actor.id,
            created_at=now,
        )
        for student_id, branch_id in allowed
    )
    await audit.record(
        db, actor, "fee.reminders_marked", "fee_reminder", None,
        detail={"marked": len(allowed), "requested": len(ids)},
    )
    await db.commit()
    return ReminderMarked(marked=len(allowed))
