"""Late fees: a new invoice for an overdue balance. The overdue invoice itself is never changed.

Each overdue invoice gets at most one late-fee invoice. The title "Late fee <invoice no>" is unique
per student and year, so running the apply step twice never charges twice.
"""

from dataclasses import dataclass
from datetime import timedelta

from fastapi import status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ApiError
from app.modules.audit import service as audit
from app.modules.fees.models import Invoice, InvoiceLine
from app.modules.fees.service import (
    _get_year,
    _invoice_no,
    _invoice_rows,
    _next_invoice_seq,
    _retry_once,
    _school_id,
    _unprocessable,
    today,
)
from app.modules.fees.tools_schemas import LateFeeApply, LateFeePreview, LateFeeResult, LateFeeRow
from app.modules.settings import service as settings_service
from app.modules.students.models import Student
from app.modules.users.models import User

LATE_FEE_PREFIX = "Late fee "
LATE_FEE_LINE = "Late fee"
LATE_FEE_DUE_DAYS = 7
_BASIS_POINTS_MAX = 10_000
_KEYS = (
    "fees.late_fee_type",
    "fees.late_fee_amount",
    "fees.late_fee_grace_days",
    "fees.late_fee_max_paise",
)


@dataclass(frozen=True)
class _Rules:
    kind: str  # none | flat | percent
    amount: int  # paise, or basis points for percent
    grace_days: int
    cap_paise: int  # 0 = no cap


@dataclass(frozen=True)
class _Candidate:
    invoice: Invoice
    student: Student
    class_name: str | None
    balance: int
    fee: int


async def _rules(db: AsyncSession, school_id: int) -> _Rules:
    values = await settings_service.resolve_many(
        db, _KEYS, settings_service.ctx_for(school_id=school_id)
    )
    return _Rules(
        kind=str(values[_KEYS[0]]),
        amount=int(values[_KEYS[1]]),
        grace_days=int(values[_KEYS[2]]),
        cap_paise=int(values[_KEYS[3]]),
    )


def _check_rules(rules: _Rules) -> None:
    if rules.kind == "percent" and rules.amount > _BASIS_POINTS_MAX:
        raise _unprocessable("The late fee percentage is set above 100%; fix it in Settings")


def _fee_for(balance: int, rules: _Rules) -> int:
    if rules.kind == "flat":
        fee = rules.amount
    elif rules.kind == "percent":
        fee = balance * rules.amount // _BASIS_POINTS_MAX
    else:
        return 0
    if rules.cap_paise > 0:
        fee = min(fee, rules.cap_paise)
    return fee


async def _candidates(
    db: AsyncSession, actor: User, year_id: int, rules: _Rules
) -> list[_Candidate]:
    """Overdue invoices of the year (in scope) with a balance, that have no late fee yet."""
    cutoff = today() - timedelta(days=rules.grace_days)
    rows = await _invoice_rows(
        db,
        [
            Invoice.academic_year_id == year_id,
            Invoice.status_cancelled.is_(False),
            Invoice.due_date < cutoff,
        ],
        actor,
    )
    if not rows:
        return []
    students = {r[0].student_id for r in rows}
    charged = {
        (sid, title)
        for sid, title in (
            await db.execute(
                select(Invoice.student_id, Invoice.title).where(
                    Invoice.academic_year_id == year_id,
                    Invoice.student_id.in_(students),
                    Invoice.title.startswith(LATE_FEE_PREFIX),
                )
            )
        ).all()
    }
    out: list[_Candidate] = []
    for inv, stu, class_name, _section, paid in rows:
        if inv.title.startswith(LATE_FEE_PREFIX):
            continue  # no late fee on a late fee
        if (inv.student_id, LATE_FEE_PREFIX + inv.invoice_no) in charged:
            continue
        balance = inv.gross_paise - inv.discount_paise - inv.carried_forward_paise - paid
        if balance <= 0:
            continue
        fee = _fee_for(balance, rules)
        if fee <= 0:
            continue
        out.append(_Candidate(inv, stu, class_name, balance, fee))
    out.sort(key=lambda c: (c.invoice.due_date, c.invoice.id))
    return out


def _row(c: _Candidate) -> LateFeeRow:
    return LateFeeRow(
        invoice_id=c.invoice.id,
        invoice_no=c.invoice.invoice_no,
        student_id=c.invoice.student_id,
        student_name=f"{c.student.first_name} {c.student.last_name}".strip(),
        admission_no=c.student.admission_no,
        class_name=c.class_name,
        title=c.invoice.title,
        due_date=c.invoice.due_date,
        balance_paise=c.balance,
        late_fee_paise=c.fee,
    )


async def preview(db: AsyncSession, actor: User, academic_year_id: int) -> LateFeePreview:
    school_id = _school_id(actor)
    year = await _get_year(db, actor, academic_year_id)
    rules = await _rules(db, school_id)
    if rules.kind == "none":
        return LateFeePreview(
            enabled=False, late_fee_type="none", items=[], count=0, total_late_fee_paise=0
        )
    _check_rules(rules)
    found = await _candidates(db, actor, year.id, rules)
    return LateFeePreview(
        enabled=True,
        late_fee_type=rules.kind,
        items=[_row(c) for c in found],
        count=len(found),
        total_late_fee_paise=sum(c.fee for c in found),
    )


async def apply(db: AsyncSession, actor: User, data: LateFeeApply) -> LateFeeResult:
    school_id = _school_id(actor)
    year = await _get_year(db, actor, data.academic_year_id)
    rules = await _rules(db, school_id)
    if rules.kind == "none":
        raise ApiError(
            status.HTTP_409_CONFLICT,
            "Late fees are switched off. Choose a late fee type in Settings first.",
            "late_fee_disabled",
        )
    _check_rules(rules)
    wanted = None if data.invoice_ids is None else set(data.invoice_ids)
    number_year = today().year
    due = today() + timedelta(days=LATE_FEE_DUE_DAYS)

    async def run() -> int:
        found = await _candidates(db, actor, year.id, rules)
        if wanted is not None:
            found = [c for c in found if c.invoice.id in wanted]
        if not found:
            return 0
        seq = await _next_invoice_seq(db, school_id, number_year)
        invoices: list[Invoice] = []
        for c in found:
            seq += 1
            invoices.append(
                Invoice(
                    school_id=school_id,
                    branch_id=c.invoice.branch_id,
                    student_id=c.invoice.student_id,
                    academic_year_id=year.id,
                    invoice_no=_invoice_no(number_year, seq),
                    title=LATE_FEE_PREFIX + c.invoice.invoice_no,
                    due_date=due,
                    gross_paise=c.fee,
                    discount_paise=0,
                    status_cancelled=False,
                    created_by=actor.id,
                )
            )
        db.add_all(invoices)
        await db.flush()
        db.add_all(
            InvoiceLine(
                invoice_id=inv.id,
                fee_head_id=None,
                description=LATE_FEE_LINE,
                amount_paise=inv.gross_paise,
            )
            for inv in invoices
        )
        await audit.record(
            db, actor, "fee.late_fee_applied", "invoice", None,
            detail={
                "created": len(invoices),
                "academic_year_id": year.id,
                "late_fee_type": rules.kind,
                "selected": wanted is not None,
            },
        )
        await db.commit()
        return len(invoices)

    created = await _retry_once(db, actor, run)
    skipped = 0 if wanted is None else len(wanted) - created
    return LateFeeResult(created=created, skipped=skipped)

