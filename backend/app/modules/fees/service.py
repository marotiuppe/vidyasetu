import csv
import io
from collections import defaultdict
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta, timezone
from typing import Any, cast

from fastapi import HTTPException, status
from sqlalchemy import and_, case, delete, exists, func, or_, select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.core.tenant import scope_branches, scope_fees, scope_students
from app.db.base import utcnow
from app.modules.academics.models import AcademicYear, SchoolClass, Section
from app.modules.audit import service as audit
from app.modules.branches.models import Branch
from app.modules.fees.models import (
    FeeHead,
    FeeStructureItem,
    Invoice,
    InvoiceLine,
    Payment,
    PaymentMethod,
    PaymentStatus,
)
from app.modules.fees.schemas import (
    CancelRequest,
    CollectionOut,
    DayTotal,
    DueRow,
    DuesOut,
    DueTotals,
    GenerateRequest,
    GenerateResult,
    HeadCreate,
    HeadUpdate,
    InvoiceCreate,
    InvoiceDetail,
    InvoiceOut,
    InvoicePage,
    InvoiceUpdate,
    LineOut,
    MethodTotal,
    PaymentCreate,
    PaymentOut,
    PaymentPage,
    PaymentTotals,
    ReverseRequest,
    StructureItemOut,
    StructureReplace,
    StudentFees,
    Totals,
)
from app.modules.schools.models import School, SchoolLogo
from app.modules.settings import service as settings_service
from app.modules.students.models import Enrollment, Guardian, Student, StudentStatus
from app.modules.users.models import User

IST = timezone(timedelta(hours=5, minutes=30))  # no DST, so a fixed offset is exact
MAX_GENERATE = 1000
MAX_COLLECTION_DAYS = 366


def today() -> date:
    return datetime.now(IST).date()


def _not_found(what: str) -> HTTPException:
    return HTTPException(status.HTTP_404_NOT_FOUND, detail=f"{what} not found")


def _conflict(detail: str) -> HTTPException:
    return HTTPException(status.HTTP_409_CONFLICT, detail=detail)


def _unprocessable(detail: str) -> HTTPException:
    return HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail=detail)


def _school_id(actor: User) -> int:
    if actor.school_id is None:  # fee writers always belong to a school
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Not allowed")
    return actor.school_id


def _blank_to_none(value: str | None) -> str | None:
    return value or None


def _full_name(first: str, last: str) -> str:
    return f"{first} {last}".strip()


async def _retry_once[T](db: AsyncSession, actor: User, fn: Callable[[], Awaitable[T]]) -> T:
    """Run `fn` (which commits); on a unique-number race roll back and run it one more time."""
    for attempt in (1, 2):
        try:
            return await fn()
        except IntegrityError:
            await db.rollback()
            await db.refresh(actor)
            if attempt == 2:
                raise _conflict("Could not complete the request, please try again") from None
    raise AssertionError("unreachable")  # pragma: no cover


# ---- lookups (always through the central scope helpers) ----


async def _get_year(db: AsyncSession, actor: User, year_id: int) -> AcademicYear:
    year: AcademicYear | None = await db.scalar(
        scope_fees(select(AcademicYear), AcademicYear, actor).where(AcademicYear.id == year_id)
    )
    if year is None:
        raise _not_found("Academic year")
    return year


async def _get_class(db: AsyncSession, actor: User, class_id: int) -> SchoolClass:
    cls: SchoolClass | None = await db.scalar(
        scope_fees(select(SchoolClass), SchoolClass, actor).where(SchoolClass.id == class_id)
    )
    if cls is None:
        raise _not_found("Class")
    return cls


async def _check_branch(db: AsyncSession, actor: User, branch_id: int | None) -> None:
    if branch_id is None:
        return
    found = await db.scalar(scope_branches(select(Branch.id), actor).where(Branch.id == branch_id))
    if found is None:
        raise _not_found("Branch")


async def _current_year_id(db: AsyncSession, actor: User) -> int | None:
    if actor.school_id is None:
        return None
    return await db.scalar(
        select(AcademicYear.id).where(
            AcademicYear.school_id == actor.school_id, AcademicYear.is_current.is_(True)
        )
    )


async def _heads_by_id(db: AsyncSession, actor: User, ids: set[int]) -> dict[int, FeeHead]:
    if not ids:
        return {}
    rows = await db.scalars(scope_fees(select(FeeHead), FeeHead, actor).where(FeeHead.id.in_(ids)))
    return {h.id: h for h in rows}


# ---- fee heads ----


async def list_heads(db: AsyncSession, actor: User) -> list[FeeHead]:
    stmt = scope_fees(select(FeeHead), FeeHead, actor)
    return list(await db.scalars(stmt.order_by(FeeHead.name_key)))


async def _head_name_taken(
    db: AsyncSession, school_id: int, key: str, except_id: int | None = None
) -> bool:
    stmt = select(FeeHead.id).where(FeeHead.school_id == school_id, FeeHead.name_key == key)
    if except_id is not None:
        stmt = stmt.where(FeeHead.id != except_id)
    return await db.scalar(stmt) is not None


async def create_head(db: AsyncSession, actor: User, data: HeadCreate) -> FeeHead:
    school_id = _school_id(actor)
    key = data.name.lower()
    if await _head_name_taken(db, school_id, key):
        raise _conflict("A fee head with this name already exists")
    head = FeeHead(school_id=school_id, name=data.name, name_key=key, is_active=True)
    db.add(head)
    try:
        await db.flush()
        await audit.record(db, actor, "fee.head_created", "fee_head", head.id)
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise _conflict("A fee head with this name already exists") from None
    return head


async def update_head(db: AsyncSession, actor: User, head_id: int, data: HeadUpdate) -> FeeHead:
    head: FeeHead | None = await db.scalar(
        scope_fees(select(FeeHead), FeeHead, actor).where(FeeHead.id == head_id)
    )
    if head is None:
        raise _not_found("Fee head")
    if data.name is not None:
        key = data.name.lower()
        if await _head_name_taken(db, head.school_id, key, head.id):
            raise _conflict("A fee head with this name already exists")
        head.name, head.name_key = data.name, key
    if data.is_active is not None:
        head.is_active = data.is_active
    try:
        await audit.record(
            db, actor, "fee.head_updated", "fee_head", head.id,
            detail={"name_changed": data.name is not None, "is_active": data.is_active},
        )
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise _conflict("A fee head with this name already exists") from None
    return head


# ---- fee structure ----


async def list_structure(
    db: AsyncSession, actor: User, academic_year_id: int | None, class_id: int | None
) -> list[StructureItemOut]:
    stmt = (
        select(FeeStructureItem, SchoolClass.name, SchoolClass.level, FeeHead.name)
        .join(SchoolClass, SchoolClass.id == FeeStructureItem.class_id)
        .join(FeeHead, FeeHead.id == FeeStructureItem.fee_head_id)
    )
    stmt = scope_fees(stmt, FeeStructureItem, actor)
    if academic_year_id is not None:
        stmt = stmt.where(FeeStructureItem.academic_year_id == academic_year_id)
    if class_id is not None:
        stmt = stmt.where(FeeStructureItem.class_id == class_id)
    stmt = stmt.order_by(SchoolClass.level, FeeStructureItem.class_id, FeeStructureItem.id)
    return [
        StructureItemOut(
            id=item.id,
            academic_year_id=item.academic_year_id,
            class_id=item.class_id,
            class_name=class_name,
            fee_head_id=item.fee_head_id,
            fee_head_name=head_name,
            amount_paise=item.amount_paise,
        )
        for item, class_name, _level, head_name in (await db.execute(stmt)).all()
    ]


async def replace_structure(
    db: AsyncSession, actor: User, data: StructureReplace
) -> list[StructureItemOut]:
    year = await _get_year(db, actor, data.academic_year_id)
    cls = await _get_class(db, actor, data.class_id)
    head_ids = [i.fee_head_id for i in data.items]
    if len(set(head_ids)) != len(head_ids):
        raise _unprocessable("Each fee head can appear only once")
    heads = await _heads_by_id(db, actor, set(head_ids))
    if len(heads) != len(set(head_ids)):
        raise _not_found("Fee head")
    if any(not h.is_active for h in heads.values()):
        raise _unprocessable("Inactive fee heads cannot be used in a structure")
    await db.execute(
        delete(FeeStructureItem).where(
            FeeStructureItem.academic_year_id == year.id, FeeStructureItem.class_id == cls.id
        )
    )
    db.add_all(
        FeeStructureItem(
            school_id=cls.school_id,
            branch_id=cls.branch_id,
            academic_year_id=year.id,
            class_id=cls.id,
            fee_head_id=i.fee_head_id,
            amount_paise=i.amount_paise,
        )
        for i in data.items
    )
    try:
        await audit.record(
            db, actor, "fee.structure_updated", "class", cls.id,
            detail={"academic_year_id": year.id, "items": len(data.items)},
            school_id=cls.school_id, branch_id=cls.branch_id,
        )
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise _conflict("The fee structure was changed meanwhile, please retry") from None
    return await list_structure(db, actor, year.id, cls.id)


# ---- numbering ----


async def _max_seq(
    db: AsyncSession, column: Any, school_col: Any, school_id: int, prefix: str
) -> int:
    last = await db.scalar(
        select(column)
        .where(school_col == school_id, column.startswith(prefix, autoescape=True))
        .order_by(func.length(column).desc(), column.desc())
        .limit(1)
    )
    if last is None:
        return 0
    try:
        return int(str(last)[len(prefix) :])
    except ValueError:
        return 0


async def _next_invoice_seq(db: AsyncSession, school_id: int, year: int) -> int:
    return await _max_seq(db, Invoice.invoice_no, Invoice.school_id, school_id, f"INV-{year}-")


def _invoice_no(year: int, seq: int) -> str:
    return f"INV-{year}-{seq:04d}"


# ---- invoice queries ----


class _Money:
    """SQL fragments for an invoice's total, amount paid (received payments) and balance."""

    def __init__(self) -> None:
        self.paid_sq = (
            select(
                Payment.invoice_id.label("invoice_id"),
                func.sum(Payment.amount_paise).label("paid"),
            )
            .where(Payment.status == PaymentStatus.RECEIVED)
            .group_by(Payment.invoice_id)
            .subquery()
        )
        self.paid = func.coalesce(self.paid_sq.c.paid, 0)
        self.total = Invoice.gross_paise - Invoice.discount_paise
        self.balance = self.total - self.paid

    def base(self, *cols: Any) -> Any:
        return (
            select(*cols)
            .select_from(Invoice)
            .join(Student, Student.id == Invoice.student_id)
            .outerjoin(self.paid_sq, self.paid_sq.c.invoice_id == Invoice.id)
        )


def _status(cancelled: bool, total: int, paid: int) -> str:
    if cancelled:
        return "cancelled"
    if total - paid <= 0:
        return "paid"
    return "partial" if paid > 0 else "unpaid"


@dataclass
class InvoiceFilters:
    academic_year_id: int | None = None
    class_id: int | None = None
    section_id: int | None = None
    student_id: int | None = None
    status: str | None = None
    q: str | None = None
    overdue: bool | None = None


def _out(
    inv: Invoice,
    stu: Student,
    class_name: str | None,
    section_name: str | None,
    paid: int,
    day: date,
) -> dict[str, Any]:
    total = inv.gross_paise - inv.discount_paise
    balance = total - paid
    return {
        "id": inv.id,
        "invoice_no": inv.invoice_no,
        "student_id": inv.student_id,
        "student_name": _full_name(stu.first_name, stu.last_name),
        "admission_no": stu.admission_no,
        "class_name": class_name,
        "section_name": section_name,
        "academic_year_id": inv.academic_year_id,
        "title": inv.title,
        "due_date": inv.due_date,
        "gross_paise": inv.gross_paise,
        "discount_paise": inv.discount_paise,
        "discount_reason": inv.discount_reason,
        "total_paise": total,
        "paid_paise": paid,
        "balance_paise": balance,
        "status": _status(inv.status_cancelled, total, paid),
        "is_overdue": (not inv.status_cancelled) and balance > 0 and inv.due_date < day,
    }


async def _invoice_rows(
    db: AsyncSession, conditions: list[Any], actor: User | None, *, order: bool = True
) -> list[tuple[Invoice, Student, str | None, str | None, int]]:
    """Invoices with student, class/section of the invoice's year and amount paid (one query).

    `actor=None` means the caller has already scoped access through the student.
    """
    m = _Money()
    stmt = (
        m.base(Invoice, Student, SchoolClass.name, Section.name, m.paid)
        .outerjoin(
            Enrollment,
            and_(
                Enrollment.student_id == Invoice.student_id,
                Enrollment.academic_year_id == Invoice.academic_year_id,
            ),
        )
        .outerjoin(SchoolClass, SchoolClass.id == Enrollment.class_id)
        .outerjoin(Section, Section.id == Enrollment.section_id)
        .where(*conditions)
    )
    if actor is not None:
        stmt = scope_fees(stmt, Invoice, actor)
    if order:
        stmt = stmt.order_by(Invoice.id.desc())
    return [(r[0], r[1], r[2], r[3], int(r[4])) for r in (await db.execute(stmt)).all()]


async def _payments_out(
    db: AsyncSession, conditions: list[Any], *, limit: int | None = None, offset: int = 0
) -> list[PaymentOut]:
    stmt = (
        select(Payment, Invoice.invoice_no, Student.first_name, Student.last_name, User.full_name)
        .join(Invoice, Invoice.id == Payment.invoice_id)
        .join(Student, Student.id == Payment.student_id)
        .join(User, User.id == Payment.received_by)
        .where(*conditions)
        .order_by(Payment.paid_on.desc(), Payment.id.desc())
    )
    if limit is not None:
        stmt = stmt.limit(limit).offset(offset)
    return [
        PaymentOut(
            id=p.id,
            receipt_no=p.receipt_no,
            invoice_id=p.invoice_id,
            invoice_no=inv_no,
            student_id=p.student_id,
            student_name=_full_name(first, last),
            amount_paise=p.amount_paise,
            method=p.method,
            reference=p.reference,
            paid_on=p.paid_on,
            status=p.status,
            received_by_name=by,
            note=p.note,
            reversed_reason=p.reversed_reason,
            created_at=p.created_at,
        )
        for p, inv_no, first, last, by in (await db.execute(stmt)).all()
    ]


async def _details(
    db: AsyncSession, rows: list[tuple[Invoice, Student, str | None, str | None, int]]
) -> list[InvoiceDetail]:
    if not rows:
        return []
    ids = [r[0].id for r in rows]
    lines: dict[int, list[LineOut]] = defaultdict(list)
    for ln in await db.scalars(
        select(InvoiceLine).where(InvoiceLine.invoice_id.in_(ids)).order_by(InvoiceLine.id)
    ):
        lines[ln.invoice_id].append(
            LineOut(
                id=ln.id,
                fee_head_id=ln.fee_head_id,
                description=ln.description,
                amount_paise=ln.amount_paise,
            )
        )
    payments: dict[int, list[PaymentOut]] = defaultdict(list)
    for p in await _payments_out(db, [Payment.invoice_id.in_(ids)]):
        payments[p.invoice_id].append(p)
    day = today()
    return [
        InvoiceDetail(
            **_out(inv, stu, cls, sec, paid, day),
            lines=lines[inv.id],
            payments=list(reversed(payments[inv.id])),  # oldest first
            cancel_reason=inv.cancel_reason,
        )
        for inv, stu, cls, sec, paid in rows
    ]


async def _detail_one(db: AsyncSession, actor: User, invoice_id: int) -> InvoiceDetail:
    rows = await _invoice_rows(db, [Invoice.id == invoice_id], actor)
    if not rows:
        raise _not_found("Invoice")
    return (await _details(db, rows))[0]


async def _lock_invoice(db: AsyncSession, actor: User, invoice_id: int) -> Invoice:
    """Fetch an in-scope invoice and lock it for the rest of the transaction.

    PostgreSQL: SELECT ... FOR UPDATE. SQLite ignores FOR UPDATE, so the following no-op UPDATE
    takes its (database-wide) write lock; either way concurrent payments, discounts and
    cancellations on one invoice are serialised and the row is re-read after the lock.
    """
    inv: Invoice | None = await db.scalar(
        scope_fees(select(Invoice), Invoice, actor)
        .where(Invoice.id == invoice_id)
        .with_for_update()
    )
    if inv is None:
        raise _not_found("Invoice")
    await db.execute(update(Invoice).where(Invoice.id == inv.id).values(updated_at=utcnow()))
    await db.refresh(inv)
    return inv


async def _received_total(db: AsyncSession, invoice_id: int) -> int:
    return int(
        await db.scalar(
            select(func.coalesce(func.sum(Payment.amount_paise), 0)).where(
                Payment.invoice_id == invoice_id, Payment.status == PaymentStatus.RECEIVED
            )
        )
        or 0
    )


# ---- invoice generation and creation ----


async def generate_invoices(db: AsyncSession, actor: User, data: GenerateRequest) -> GenerateResult:
    school_id = _school_id(actor)
    year = await _get_year(db, actor, data.academic_year_id)
    if data.class_id is not None:
        await _get_class(db, actor, data.class_id)
    if data.section_id is not None:
        sec = await db.scalar(
            scope_fees(select(Section.id), Section, actor).where(Section.id == data.section_id)
        )
        if sec is None:
            raise _not_found("Section")
    wanted_heads = set(data.fee_head_ids or [])
    if wanted_heads and len(await _heads_by_id(db, actor, wanted_heads)) != len(wanted_heads):
        raise _not_found("Fee head")

    ids = set(data.student_ids or [])
    if ids:
        in_scope = set(
            await db.scalars(scope_students(select(Student.id), actor).where(Student.id.in_(ids)))
        )
        if in_scope != ids:
            raise _not_found("Student")

    enrol = and_(Enrollment.student_id == Student.id, Enrollment.academic_year_id == year.id)
    stmt = scope_students(
        select(Student.id, Student.branch_id, Enrollment.class_id).join(Enrollment, enrol), actor
    )
    if ids:
        stmt = stmt.where(Student.id.in_(ids))
    else:
        stmt = stmt.where(Student.status == StudentStatus.ACTIVE)
    if data.class_id is not None:
        stmt = stmt.where(Enrollment.class_id == data.class_id)
    if data.section_id is not None:
        stmt = stmt.where(Enrollment.section_id == data.section_id)
    if ids:
        enrolled = set(
            await db.scalars(
                select(Enrollment.student_id).where(
                    Enrollment.academic_year_id == year.id, Enrollment.student_id.in_(ids)
                )
            )
        )
        if enrolled != ids:
            raise _unprocessable("Some students are not enrolled in this academic year")
    targets = [(sid, bid, cid) for sid, bid, cid in (await db.execute(stmt.order_by(Student.id)))]
    if len(targets) > MAX_GENERATE:
        raise _unprocessable(f"At most {MAX_GENERATE} students per call")

    async def run() -> GenerateResult:
        result = GenerateResult(created=0, skipped_existing=0, skipped_no_structure=0)
        if not targets:
            return result
        student_ids = [t[0] for t in targets]
        existing = set(
            await db.scalars(
                select(Invoice.student_id).where(
                    Invoice.academic_year_id == year.id,
                    Invoice.title == data.title,
                    Invoice.student_id.in_(student_ids),
                )
            )
        )
        sel = (
            select(
                FeeStructureItem.class_id,
                FeeStructureItem.fee_head_id,
                FeeStructureItem.amount_paise,
                FeeHead.name,
            )
            .join(FeeHead, FeeHead.id == FeeStructureItem.fee_head_id)
            .where(
                FeeStructureItem.academic_year_id == year.id,
                FeeStructureItem.class_id.in_({t[2] for t in targets}),
                FeeHead.is_active.is_(True),
            )
            .order_by(FeeStructureItem.id)
        )
        if wanted_heads:
            sel = sel.where(FeeStructureItem.fee_head_id.in_(wanted_heads))
        by_class: dict[int, list[tuple[int, int, str]]] = defaultdict(list)
        for cid, hid, amount, name in await db.execute(sel):
            by_class[cid].append((hid, amount, name))

        number_year = today().year
        seq = await _next_invoice_seq(db, school_id, number_year)
        pending: list[tuple[Invoice, list[tuple[int, int, str]]]] = []
        for sid, bid, cid in targets:
            if sid in existing:
                result.skipped_existing += 1
            elif not by_class.get(cid):
                result.skipped_no_structure += 1
            else:
                items = by_class[cid]
                seq += 1
                inv = Invoice(
                    school_id=school_id,
                    branch_id=bid,
                    student_id=sid,
                    academic_year_id=year.id,
                    invoice_no=_invoice_no(number_year, seq),
                    title=data.title,
                    due_date=data.due_date,
                    gross_paise=sum(i[1] for i in items),
                    discount_paise=0,
                    status_cancelled=False,
                    created_by=actor.id,
                )
                pending.append((inv, items))
        db.add_all(inv for inv, _ in pending)
        await db.flush()
        db.add_all(
            InvoiceLine(invoice_id=inv.id, fee_head_id=hid, description=name, amount_paise=amount)
            for inv, items in pending
            for hid, amount, name in items
        )
        if pending:
            await audit.record(
                db, actor, "fee.invoice_created", "invoice", None,
                detail={
                    "batch": True,
                    "academic_year_id": year.id,
                    "created": len(pending),
                    "skipped_existing": result.skipped_existing,
                    "skipped_no_structure": result.skipped_no_structure,
                },
            )
        await db.commit()
        result.created = len(pending)
        return result

    return await _retry_once(db, actor, run)


async def create_invoice(db: AsyncSession, actor: User, data: InvoiceCreate) -> InvoiceDetail:
    school_id = _school_id(actor)
    year = await _get_year(db, actor, data.academic_year_id)
    student = await db.scalar(
        scope_students(select(Student), actor).where(Student.id == data.student_id)
    )
    if student is None:
        raise _not_found("Student")
    head_ids = {ln.fee_head_id for ln in data.lines if ln.fee_head_id is not None}
    if len(await _heads_by_id(db, actor, head_ids)) != len(head_ids):
        raise _unprocessable("Unknown fee head")

    async def run() -> int:
        dup = await db.scalar(
            select(Invoice.id).where(
                Invoice.student_id == student.id,
                Invoice.academic_year_id == year.id,
                Invoice.title == data.title,
            )
        )
        if dup is not None:
            raise _conflict("An invoice with this title already exists for the student and year")
        number_year = today().year
        seq = await _next_invoice_seq(db, school_id, number_year) + 1
        inv = Invoice(
            school_id=school_id,
            branch_id=student.branch_id,
            student_id=student.id,
            academic_year_id=year.id,
            invoice_no=_invoice_no(number_year, seq),
            title=data.title,
            due_date=data.due_date,
            gross_paise=sum(ln.amount_paise for ln in data.lines),
            discount_paise=0,
            status_cancelled=False,
            created_by=actor.id,
        )
        db.add(inv)
        await db.flush()
        db.add_all(
            InvoiceLine(
                invoice_id=inv.id,
                fee_head_id=ln.fee_head_id,
                description=ln.description,
                amount_paise=ln.amount_paise,
            )
            for ln in data.lines
        )
        await audit.record(
            db, actor, "fee.invoice_created", "invoice", inv.id,
            detail={"lines": len(data.lines), "amount_paise": inv.gross_paise},
            school_id=inv.school_id, branch_id=inv.branch_id,
        )
        await db.commit()
        return inv.id

    invoice_id = await _retry_once(db, actor, run)
    return await _detail_one(db, actor, invoice_id)


# ---- invoice listing ----


async def _filter_conditions(
    db: AsyncSession, actor: User, f: InvoiceFilters, m: _Money, day: date
) -> list[Any]:
    cond: list[Any] = []
    if f.academic_year_id is not None:
        await _get_year(db, actor, f.academic_year_id)
        cond.append(Invoice.academic_year_id == f.academic_year_id)
    if f.student_id is not None:
        cond.append(Invoice.student_id == f.student_id)
    if f.class_id is not None or f.section_id is not None:
        year_id = f.academic_year_id or await _current_year_id(db, actor)
        en = aliased(Enrollment)
        enrol = [
            en.student_id == Invoice.student_id,
            en.academic_year_id == (year_id if year_id is not None else -1),
        ]
        if f.class_id is not None:
            enrol.append(en.class_id == f.class_id)
        if f.section_id is not None:
            enrol.append(en.section_id == f.section_id)
        cond.append(exists().where(*enrol))
    if f.status is not None:
        not_cancelled = Invoice.status_cancelled.is_(False)
        by_status = {
            "cancelled": Invoice.status_cancelled.is_(True),
            "paid": and_(not_cancelled, m.balance <= 0),
            "partial": and_(not_cancelled, m.balance > 0, m.paid > 0),
            "unpaid": and_(not_cancelled, m.balance > 0, m.paid <= 0),
        }
        cond.append(by_status[f.status])
    if f.overdue is not None:
        is_overdue = and_(
            Invoice.status_cancelled.is_(False), m.balance > 0, Invoice.due_date < day
        )
        cond.append(is_overdue if f.overdue else ~is_overdue)
    if f.q:
        term = f.q.strip().lower()
        if term:
            cond.append(
                or_(
                    func.lower(Invoice.invoice_no).contains(term, autoescape=True),
                    func.lower(Student.admission_no).contains(term, autoescape=True),
                    func.lower(Student.first_name + " " + Student.last_name).contains(
                        term, autoescape=True
                    ),
                )
            )
    return cond


async def list_invoices(
    db: AsyncSession, actor: User, f: InvoiceFilters, page: int, page_size: int
) -> InvoicePage:
    day = today()
    m = _Money()
    cond = await _filter_conditions(db, actor, f, m, day)
    count_stmt = scope_fees(m.base(func.count()).where(*cond), Invoice, actor)
    total = int(await db.scalar(count_stmt) or 0)

    live = Invoice.status_cancelled.is_(False)
    totals_stmt = scope_fees(
        m.base(
            func.coalesce(func.sum(case((live, m.total), else_=0)), 0),
            func.coalesce(func.sum(case((live, m.paid), else_=0)), 0),
            func.coalesce(func.sum(case((live, m.balance), else_=0)), 0),
        ).where(*cond),
        Invoice,
        actor,
    )
    billed, paid, balance = (await db.execute(totals_stmt)).one()

    stmt = (
        m.base(Invoice, Student, SchoolClass.name, Section.name, m.paid)
        .outerjoin(
            Enrollment,
            and_(
                Enrollment.student_id == Invoice.student_id,
                Enrollment.academic_year_id == Invoice.academic_year_id,
            ),
        )
        .outerjoin(SchoolClass, SchoolClass.id == Enrollment.class_id)
        .outerjoin(Section, Section.id == Enrollment.section_id)
        .where(*cond)
    )
    stmt = scope_fees(stmt, Invoice, actor)
    stmt = stmt.order_by(Invoice.id.desc()).limit(page_size).offset((page - 1) * page_size)
    rows = (await db.execute(stmt)).all()
    return InvoicePage(
        items=[InvoiceOut(**_out(r[0], r[1], r[2], r[3], int(r[4]), day)) for r in rows],
        total=total,
        page=page,
        page_size=page_size,
        totals=Totals(billed_paise=int(billed), paid_paise=int(paid), balance_paise=int(balance)),
    )


async def get_invoice(db: AsyncSession, actor: User, invoice_id: int) -> InvoiceDetail:
    return await _detail_one(db, actor, invoice_id)


# ---- invoice changes ----


async def update_invoice(
    db: AsyncSession, actor: User, invoice_id: int, data: InvoiceUpdate
) -> InvoiceDetail:
    inv = await _lock_invoice(db, actor, invoice_id)
    if inv.status_cancelled:
        raise _conflict("A cancelled invoice cannot be changed")
    if data.due_date is not None:
        inv.due_date = data.due_date
    if data.discount_paise is not None:
        paid = await _received_total(db, inv.id)
        if data.discount_paise > inv.gross_paise - paid:
            raise _unprocessable("Discount cannot exceed the amount not yet paid")
        inv.discount_paise = data.discount_paise
    if "discount_reason" in data.model_fields_set:
        inv.discount_reason = _blank_to_none(data.discount_reason)
    await db.commit()
    return await _detail_one(db, actor, invoice_id)


async def cancel_invoice(
    db: AsyncSession, actor: User, invoice_id: int, data: CancelRequest
) -> InvoiceDetail:
    inv = await _lock_invoice(db, actor, invoice_id)
    if inv.status_cancelled:
        raise _conflict("Invoice is already cancelled")
    if await _received_total(db, inv.id) > 0:
        raise _conflict("An invoice with received payments cannot be cancelled; reverse them first")
    inv.status_cancelled = True
    inv.cancel_reason = data.reason
    await db.commit()
    return await _detail_one(db, actor, invoice_id)


# ---- payments ----


async def record_payment(
    db: AsyncSession, actor: User, invoice_id: int, data: PaymentCreate
) -> PaymentOut:
    school_id = _school_id(actor)
    day = today()
    paid_on = data.paid_on or day
    if paid_on > day:
        raise _unprocessable("Payment date cannot be in the future")

    async def run() -> int:
        inv = await _lock_invoice(db, actor, invoice_id)
        if inv.status_cancelled:
            raise _conflict("Cannot record a payment on a cancelled invoice")
        paid = await _received_total(db, inv.id)
        balance = inv.gross_paise - inv.discount_paise - paid
        if data.amount_paise > balance:
            raise _conflict("Amount exceeds the invoice balance")
        number_year = day.year
        prefix = await settings_service.get_str(db, "fees.receipt_prefix", school_id=school_id)
        receipt_prefix = f"{prefix or 'RCT'}-{number_year}-"
        seq = (
            await _max_seq(db, Payment.receipt_no, Payment.school_id, school_id, receipt_prefix)
            + 1
        )
        payment = Payment(
            school_id=school_id,
            branch_id=inv.branch_id,
            invoice_id=inv.id,
            student_id=inv.student_id,
            receipt_no=f"{receipt_prefix}{seq:05d}",
            amount_paise=data.amount_paise,
            method=data.method,
            reference=_blank_to_none(data.reference),
            paid_on=paid_on,
            note=_blank_to_none(data.note),
            status=PaymentStatus.RECEIVED,
            received_by=actor.id,
        )
        db.add(payment)
        await db.flush()
        pid = payment.id
        await db.commit()
        return pid

    payment_id = await _retry_once(db, actor, run)
    return (await _payments_out(db, [Payment.id == payment_id]))[0]


async def reverse_payment(
    db: AsyncSession, actor: User, payment_id: int, data: ReverseRequest
) -> PaymentOut:
    payment = await db.scalar(
        scope_fees(select(Payment.id), Payment, actor).where(Payment.id == payment_id)
    )
    if payment is None:
        raise _not_found("Payment")
    result = cast(
        CursorResult[Any],
        await db.execute(
            update(Payment)
            .where(Payment.id == payment_id, Payment.status == PaymentStatus.RECEIVED)
            .values(
                status=PaymentStatus.REVERSED,
                reversed_reason=data.reason,
                reversed_by=actor.id,
                reversed_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )
        ),
    )
    if result.rowcount == 0:
        await db.rollback()
        raise _conflict("Payment is already reversed")
    await db.commit()
    return (await _payments_out(db, [Payment.id == payment_id]))[0]


async def list_payments(
    db: AsyncSession,
    actor: User,
    *,
    date_from: date | None,
    date_to: date | None,
    method: PaymentMethod | None,
    invoice_id: int | None,
    student_id: int | None,
    pay_status: PaymentStatus | None,
    page: int,
    page_size: int,
) -> PaymentPage:
    cond: list[Any] = []
    if date_from is not None:
        cond.append(Payment.paid_on >= date_from)
    if date_to is not None:
        cond.append(Payment.paid_on <= date_to)
    if method is not None:
        cond.append(Payment.method == method)
    if invoice_id is not None:
        cond.append(Payment.invoice_id == invoice_id)
    if student_id is not None:
        cond.append(Payment.student_id == student_id)
    if pay_status is not None:
        cond.append(Payment.status == pay_status)
    agg = scope_fees(
        select(
            func.count(),
            func.coalesce(
                func.sum(
                    case((Payment.status == PaymentStatus.RECEIVED, Payment.amount_paise), else_=0)
                ),
                0,
            ),
        ).where(*cond),
        Payment,
        actor,
    )
    total, received = (await db.execute(agg)).one()
    scope = scope_fees(select(Payment.id), Payment, actor).where(*cond)
    items = await _payments_out(
        db,
        [Payment.id.in_(scope.order_by(None))],
        limit=page_size,
        offset=(page - 1) * page_size,
    )
    return PaymentPage(
        items=items,
        total=int(total),
        page=page,
        page_size=page_size,
        totals=PaymentTotals(received_paise=int(received)),
    )


# ---- dues ----


async def _dues_rows(
    db: AsyncSession,
    actor: User,
    academic_year_id: int | None,
    branch_id: int | None,
    class_id: int | None,
    section_id: int | None,
    min_balance_paise: int,
) -> DuesOut:
    day = today()
    if academic_year_id is not None:
        await _get_year(db, actor, academic_year_id)
    await _check_branch(db, actor, branch_id)
    if class_id is not None:
        await _get_class(db, actor, class_id)
    if section_id is not None:
        sec = await db.scalar(
            scope_fees(select(Section.id), Section, actor).where(Section.id == section_id)
        )
        if sec is None:
            raise _not_found("Section")
    year_id = academic_year_id or await _current_year_id(db, actor)

    m = _Money()
    balance_sum = func.sum(m.balance)
    stmt = (
        m.base(
            Student.id,
            Student.first_name,
            Student.last_name,
            Student.admission_no,
            SchoolClass.name,
            Section.name,
            Guardian.full_name,
            Guardian.phone,
            func.sum(m.total),
            func.sum(m.paid),
            balance_sum,
            func.sum(case((Invoice.due_date < day, m.balance), else_=0)),
            func.min(case((m.balance > 0, Invoice.due_date))),
        )
        .outerjoin(
            Enrollment,
            and_(
                Enrollment.student_id == Student.id,
                Enrollment.academic_year_id == (year_id if year_id is not None else -1),
            ),
        )
        .outerjoin(SchoolClass, SchoolClass.id == Enrollment.class_id)
        .outerjoin(Section, Section.id == Enrollment.section_id)
        .outerjoin(Guardian, and_(Guardian.student_id == Student.id, Guardian.is_primary.is_(True)))
        .where(Invoice.status_cancelled.is_(False))
        .group_by(
            Student.id,
            Student.first_name,
            Student.last_name,
            Student.admission_no,
            SchoolClass.name,
            Section.name,
            Guardian.full_name,
            Guardian.phone,
        )
        .having(balance_sum >= max(1, min_balance_paise))
        .order_by(balance_sum.desc(), Student.id)
    )
    stmt = scope_fees(stmt, Invoice, actor)
    if academic_year_id is not None:
        stmt = stmt.where(Invoice.academic_year_id == academic_year_id)
    if branch_id is not None:
        stmt = stmt.where(Invoice.branch_id == branch_id)
    if class_id is not None:
        stmt = stmt.where(Enrollment.class_id == class_id)
    if section_id is not None:
        stmt = stmt.where(Enrollment.section_id == section_id)
    items = [
        DueRow(
            student_id=r[0],
            student_name=_full_name(r[1], r[2]),
            admission_no=r[3],
            class_name=r[4],
            section_name=r[5],
            guardian_name=r[6],
            guardian_phone=r[7],
            billed_paise=int(r[8]),
            paid_paise=int(r[9]),
            balance_paise=int(r[10]),
            overdue_paise=int(r[11]),
            oldest_due_date=_to_date(r[12]),
        )
        for r in (await db.execute(stmt)).all()
    ]
    return DuesOut(
        items=items,
        totals=DueTotals(
            billed_paise=sum(i.billed_paise for i in items),
            paid_paise=sum(i.paid_paise for i in items),
            balance_paise=sum(i.balance_paise for i in items),
            overdue_paise=sum(i.overdue_paise for i in items),
        ),
    )


def _to_date(value: Any) -> date | None:
    """SQLite returns min() over a date expression as text; PostgreSQL returns a date."""
    if value is None:
        return None
    return date.fromisoformat(str(value)[:10])


async def dues(
    db: AsyncSession,
    actor: User,
    academic_year_id: int | None,
    branch_id: int | None,
    class_id: int | None,
    section_id: int | None,
    min_balance_paise: int,
) -> DuesOut:
    return await _dues_rows(
        db, actor, academic_year_id, branch_id, class_id, section_id, min_balance_paise
    )


def _csv_cell(value: Any) -> Any:
    """Neutralise spreadsheet formulas in text cells."""
    if isinstance(value, str) and value[:1] in ("=", "+", "-", "@", "\t", "\r"):
        return "'" + value
    return value


DUES_COLUMNS = [
    "student_id",
    "student_name",
    "admission_no",
    "class_name",
    "section_name",
    "guardian_name",
    "guardian_phone",
    "billed_paise",
    "paid_paise",
    "balance_paise",
    "overdue_paise",
    "oldest_due_date",
]


async def dues_csv(
    db: AsyncSession,
    actor: User,
    academic_year_id: int | None,
    branch_id: int | None,
    class_id: int | None,
    section_id: int | None,
    min_balance_paise: int,
) -> str:
    out = await _dues_rows(
        db, actor, academic_year_id, branch_id, class_id, section_id, min_balance_paise
    )
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(DUES_COLUMNS)
    for item in out.items:
        row = item.model_dump()
        writer.writerow([_csv_cell("" if row[c] is None else row[c]) for c in DUES_COLUMNS])
    return buf.getvalue()


# ---- collection report ----


async def collection(
    db: AsyncSession,
    actor: User,
    date_from: date | None,
    date_to: date | None,
    branch_id: int | None,
) -> CollectionOut:
    day = today()
    end = date_to or day
    start = date_from or day.replace(day=1)
    if start > end:
        raise _unprocessable("'from' must not be after 'to'")
    if (end - start).days + 1 > MAX_COLLECTION_DAYS:
        raise _unprocessable(f"The range can span at most {MAX_COLLECTION_DAYS} days")
    await _check_branch(db, actor, branch_id)
    cond = [
        Payment.status == PaymentStatus.RECEIVED,
        Payment.paid_on >= start,
        Payment.paid_on <= end,
    ]
    if branch_id is not None:
        cond.append(Payment.branch_id == branch_id)
    by_method_stmt = scope_fees(
        select(Payment.method, func.sum(Payment.amount_paise), func.count())
        .where(*cond)
        .group_by(Payment.method),
        Payment,
        actor,
    )
    by_method = [
        MethodTotal(method=mth, total_paise=int(total), count=int(cnt))
        for mth, total, cnt in (await db.execute(by_method_stmt)).all()
    ]
    by_day_stmt = scope_fees(
        select(Payment.paid_on, func.sum(Payment.amount_paise))
        .where(*cond)
        .group_by(Payment.paid_on)
        .order_by(Payment.paid_on),
        Payment,
        actor,
    )
    by_day = [
        DayTotal(date=d, total_paise=int(total))
        for d, total in (await db.execute(by_day_stmt)).all()
    ]
    return CollectionOut(
        from_=start,
        to=end,
        total_paise=sum(m.total_paise for m in by_method),
        count=sum(m.count for m in by_method),
        by_method=sorted(by_method, key=lambda m: m.method.value),
        by_day=by_day,
    )


# ---- student view (staff in scope, linked parent / student) ----


async def student_fees(db: AsyncSession, actor: User, student_id: int) -> StudentFees:
    await settings_service.require_family_portal(db, actor, "portal.parent_sees_fees")
    student = await db.scalar(
        scope_students(select(Student.id), actor).where(Student.id == student_id)
    )
    if student is None:
        raise _not_found("Student")
    rows = await _invoice_rows(
        db, [Invoice.student_id == student_id, Invoice.status_cancelled.is_(False)], None
    )
    invoices = await _details(db, rows)
    return StudentFees(
        student_id=student_id,
        invoices=invoices,
        summary=Totals(
            billed_paise=sum(i.total_paise for i in invoices),
            paid_paise=sum(i.paid_paise for i in invoices),
            balance_paise=sum(i.balance_paise for i in invoices),
        ),
    )


# ---- receipt ----


async def receipt_data(db: AsyncSession, actor: User, payment_id: int) -> dict[str, Any]:
    await settings_service.require_family_portal(db, actor, "portal.parent_sees_fees")
    stmt = scope_students(
        select(Payment, Invoice, Student, School.name, User.full_name)
        .join(Student, Student.id == Payment.student_id)
        .join(Invoice, Invoice.id == Payment.invoice_id)
        .join(School, School.id == Payment.school_id)
        .join(User, User.id == Payment.received_by),
        actor,
    ).where(Payment.id == payment_id)
    row = (await db.execute(stmt)).first()
    if row is None:
        raise _not_found("Payment")
    payment, inv, stu, school_name, received_by = row
    class_name, section_name = None, None
    enrol = (
        await db.execute(
            select(SchoolClass.name, Section.name)
            .select_from(Enrollment)
            .join(SchoolClass, SchoolClass.id == Enrollment.class_id)
            .outerjoin(Section, Section.id == Enrollment.section_id)
            .where(
                Enrollment.student_id == stu.id,
                Enrollment.academic_year_id == inv.academic_year_id,
            )
        )
    ).first()
    if enrol is not None:
        class_name, section_name = enrol
    paid = await _received_total(db, inv.id)
    total = inv.gross_paise - inv.discount_paise
    logo_png = await db.scalar(
        select(SchoolLogo.data).where(SchoolLogo.school_id == payment.school_id)
    )
    return {
        "school_name": school_name,
        "logo_png": logo_png,
        "receipt_no": payment.receipt_no,
        "paid_on": payment.paid_on,
        "student_name": _full_name(stu.first_name, stu.last_name),
        "admission_no": stu.admission_no,
        "class_name": class_name,
        "section_name": section_name,
        "invoice_no": inv.invoice_no,
        "invoice_title": inv.title,
        "invoice_total_paise": total,
        "amount_paise": payment.amount_paise,
        "paid_so_far_paise": paid,
        "balance_paise": total - paid,
        "method": payment.method.value,
        "reference": payment.reference,
        "received_by": received_by,
        "note": payment.note,
        "reversed": payment.status == PaymentStatus.REVERSED,
        "reversed_reason": payment.reversed_reason,
        "footer": await settings_service.get_str(
            db, "fees.receipt_footer", school_id=payment.school_id
        ),
    }
