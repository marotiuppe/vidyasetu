"""Year-end promotion: preview, apply (one transaction), batch history and undo.

Enrolments go through the students service and balances and invoice numbers through the fees
service, so promotion never duplicates their rules. Every write is audited without personal
values (student ids and counts only).
"""

from collections import Counter
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from fastapi import status
from sqlalchemy import and_, delete, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.core.errors import ApiError
from app.core.tenant import scope_promotion_batches, scope_students, scope_tenant
from app.db.base import as_utc, utcnow
from app.modules.academics.models import AcademicYear, SchoolClass, Section
from app.modules.attendance.models import AttendanceRecord
from app.modules.audit import service as audit
from app.modules.branches.models import Branch
from app.modules.fees import service as fees_service
from app.modules.fees.models import Invoice, Payment
from app.modules.promotion.models import PromotionAction, PromotionBatch, PromotionItem
from app.modules.promotion.schemas import (
    MAX_CANDIDATES,
    ApplyItem,
    ApplyRequest,
    BatchDetail,
    BatchItemOut,
    BatchOut,
    CandidateOut,
    ClassOption,
    PreviewOut,
    PreviewRequest,
    SectionOption,
    SkippedOut,
)
from app.modules.settings import service as settings_service
from app.modules.students import service as students_service
from app.modules.students.models import Enrollment, Student, StudentStatus
from app.modules.students.schemas import EnrollmentIn
from app.modules.users.models import Role, User

CARRY_DUE_DAYS = 30
CONTINUING = frozenset({PromotionAction.PROMOTED, PromotionAction.DETAINED})
_STATUS_FOR: dict[PromotionAction, StudentStatus] = {
    PromotionAction.PROMOTED: StudentStatus.ACTIVE,
    PromotionAction.DETAINED: StudentStatus.ACTIVE,
    PromotionAction.LEFT: StudentStatus.LEFT,
    PromotionAction.PASSED_OUT: StudentStatus.PASSED_OUT,
    PromotionAction.TRANSFERRED: StudentStatus.TRANSFERRED,
}


def _not_found(what: str) -> ApiError:
    return ApiError(status.HTTP_404_NOT_FOUND, f"{what} not found", "not_found")


def _unprocessable(detail: str, code: str) -> ApiError:
    return ApiError(status.HTTP_422_UNPROCESSABLE_ENTITY, detail, code)


def _conflict(detail: str, code: str) -> ApiError:
    return ApiError(status.HTTP_409_CONFLICT, detail, code)


def _forbidden(detail: str, code: str) -> ApiError:
    return ApiError(status.HTTP_403_FORBIDDEN, detail, code)


def _school_id(actor: User) -> int:
    if actor.school_id is None:  # staff always belong to a school
        raise _forbidden("Not allowed", "forbidden")
    return actor.school_id


def _full_name(first: str, last: str) -> str:
    return f"{first} {last}".strip()


async def _years(
    db: AsyncSession, actor: User, from_id: int, to_id: int
) -> tuple[AcademicYear, AcademicYear]:
    years = {
        y.id: y
        for y in await db.scalars(
            select(AcademicYear).where(
                AcademicYear.school_id == _school_id(actor),
                AcademicYear.id.in_({from_id, to_id}),
            )
        )
    }
    if from_id not in years or to_id not in years:
        raise _not_found("Academic year")
    frm, to = years[from_id], years[to_id]
    if to.start_date <= frm.start_date:
        raise _unprocessable("The target year must start after the source year", "year_order")
    return frm, to


def _batch_out(batch: PromotionBatch, skipped: list[SkippedOut]) -> BatchOut:
    return BatchOut(
        id=batch.id,
        from_year_id=batch.from_year_id,
        to_year_id=batch.to_year_id,
        carry_over=batch.carry_over,
        created_at=batch.created_at,
        undo_until=batch.undo_until,
        undone_at=batch.undone_at,
        promoted=batch.promoted,
        detained=batch.detained,
        left=batch.left,
        passed_out=batch.passed_out,
        transferred=batch.transferred,
        carried_invoices=batch.carried_invoices,
        carried_paise=batch.carried_paise,
        skipped=skipped,
    )


# ---- preview ----


@dataclass(frozen=True)
class _Suggestion:
    action: PromotionAction
    class_id: int | None
    class_name: str | None
    branch_name: str | None
    cross_branch: bool


async def _suggestion(db: AsyncSession, school_id: int, cls: SchoolClass) -> _Suggestion:
    """Next class in the same branch; else the next level in another branch (owner only to
    apply); else the student passes out."""
    nxt = (
        await db.execute(
            select(SchoolClass.id, SchoolClass.name, SchoolClass.branch_id, Branch.name)
            .join(Branch, Branch.id == SchoolClass.branch_id)
            .where(SchoolClass.school_id == school_id, SchoolClass.level == cls.level + 1)
            .order_by(SchoolClass.id)
        )
    ).all()
    same = next((r for r in nxt if r[2] == cls.branch_id), None)
    other = next((r for r in nxt if r[2] != cls.branch_id), None)
    if same is not None:
        return _Suggestion(PromotionAction.PROMOTED, same[0], same[1], same[3], False)
    if other is not None:
        return _Suggestion(PromotionAction.PROMOTED, other[0], other[1], other[3], True)
    return _Suggestion(PromotionAction.PASSED_OUT, None, None, None, False)


async def preview(db: AsyncSession, actor: User, data: PreviewRequest) -> PreviewOut:
    school_id = _school_id(actor)
    frm, to = await _years(db, actor, data.from_year_id, data.to_year_id)
    cls = await db.scalar(
        scope_tenant(select(SchoolClass), SchoolClass, actor).where(SchoolClass.id == data.class_id)
    )
    if cls is None:
        raise _not_found("Class")
    if data.section_id is not None:
        found = await db.scalar(
            scope_tenant(select(Section.id), Section, actor).where(
                Section.id == data.section_id, Section.class_id == cls.id
            )
        )
        if found is None:
            raise _not_found("Section")

    base = (
        select(Student, Enrollment.roll_no, Section.name)
        .select_from(Student)
        .join(
            Enrollment,
            and_(Enrollment.student_id == Student.id, Enrollment.academic_year_id == frm.id),
        )
        .outerjoin(Section, Section.id == Enrollment.section_id)
        .where(Enrollment.class_id == cls.id, Student.status == StudentStatus.ACTIVE)
    )
    stmt = scope_students(base, actor)
    if data.section_id is not None:
        stmt = stmt.where(Enrollment.section_id == data.section_id)
    stmt = stmt.order_by(Enrollment.roll_no.is_(None), Enrollment.roll_no, Student.id).limit(
        MAX_CANDIDATES + 1
    )
    rows = list((await db.execute(stmt)).all())
    truncated = len(rows) > MAX_CANDIDATES
    rows = rows[:MAX_CANDIDATES]
    ids = [r[0].id for r in rows]

    already = set(
        await db.scalars(
            select(Enrollment.student_id).where(
                Enrollment.academic_year_id == to.id, Enrollment.student_id.in_(ids)
            )
        )
    )
    balances = await fees_service.open_balances(db, frm.id, ids)

    options = (
        await db.execute(
            scope_tenant(
                select(
                    SchoolClass.id,
                    SchoolClass.name,
                    SchoolClass.branch_id,
                    Branch.name,
                    SchoolClass.level,
                ).join(Branch, Branch.id == SchoolClass.branch_id),
                SchoolClass,
                actor,
            ).order_by(SchoolClass.level, Branch.name, SchoolClass.name)
        )
    ).all()
    sections = (
        await db.execute(
            scope_tenant(select(Section), Section, actor)
            .where(Section.class_id.in_([o[0] for o in options]))
            .order_by(Section.class_id, Section.name)
        )
    ).scalars()

    sugg = await _suggestion(db, school_id, cls)
    hide_target = sugg.cross_branch and actor.role != Role.SCHOOL_OWNER
    candidates = [
        CandidateOut(
            student_id=stu.id,
            name=_full_name(stu.first_name, stu.last_name),
            admission_no=stu.admission_no,
            roll_no=roll_no,
            from_class=cls.name,
            from_section=sec_name,
            suggested_action=sugg.action,
            suggested_to_class_id=None if hide_target else sugg.class_id,
            suggested_to_class_name=None if hide_target else sugg.class_name,
            suggested_to_branch_name=None if hide_target else sugg.branch_name,
            needs_owner=sugg.cross_branch,
            dues_paise=sum(b for _, b in balances.get(stu.id, [])),
            already_enrolled=stu.id in already,
        )
        for stu, roll_no, sec_name in rows
    ]
    return PreviewOut(
        candidates=candidates,
        truncated=truncated,
        class_options=[
            ClassOption(id=cid, name=name, branch_id=bid, branch_name=bname, level=level)
            for cid, name, bid, bname, level in options
        ],
        sections=[SectionOption(id=s.id, class_id=s.class_id, name=s.name) for s in sections],
    )


# ---- apply ----


@dataclass
class _Plan:
    item: ApplyItem
    student: Student
    from_enrollment: Enrollment
    from_class: SchoolClass
    target: SchoolClass | None  # the class for the new enrolment (promoted / detained)


def _target_class(
    item: ApplyItem,
    student: Student,
    from_class: SchoolClass,
    targets: dict[int, SchoolClass],
    actor: User,
) -> SchoolClass | None:
    if item.action == PromotionAction.PROMOTED:
        if item.to_class_id is None:
            raise _unprocessable("Choose the class to promote the student to", "class_required")
        target = targets[item.to_class_id]
        if target.branch_id != student.branch_id and actor.role != Role.SCHOOL_OWNER:
            raise _forbidden(
                "Only the school owner can move a student to another branch",
                "cross_branch_forbidden",
            )
        return target
    if item.action == PromotionAction.DETAINED:
        if item.to_class_id is not None and item.to_class_id != from_class.id:
            raise _unprocessable("Detained students stay in their class", "class_mismatch")
        return from_class
    return None


async def apply(db: AsyncSession, actor: User, data: ApplyRequest) -> BatchOut:
    school_id = _school_id(actor)
    frm, to = await _years(db, actor, data.from_year_id, data.to_year_id)
    ids = [i.student_id for i in data.items]
    if len(set(ids)) != len(ids):
        raise _unprocessable("Each student can appear only once", "duplicate_student")

    students = {
        s.id: s
        for s in await db.scalars(scope_students(select(Student), actor).where(Student.id.in_(ids)))
    }
    if len(students) != len(ids):
        raise _not_found("Student")
    from_rows = (
        await db.execute(
            select(Enrollment, SchoolClass)
            .join(SchoolClass, SchoolClass.id == Enrollment.class_id)
            .where(Enrollment.academic_year_id == frm.id, Enrollment.student_id.in_(ids))
        )
    ).all()
    from_by_student = {enr.student_id: (enr, cls) for enr, cls in from_rows}
    enrolled_next = set(
        await db.scalars(
            select(Enrollment.student_id).where(
                Enrollment.academic_year_id == to.id, Enrollment.student_id.in_(ids)
            )
        )
    )
    class_ids = {i.to_class_id for i in data.items if i.to_class_id is not None}
    targets: dict[int, SchoolClass] = {}
    if class_ids:
        targets = {
            c.id: c
            for c in await db.scalars(
                select(SchoolClass).where(
                    SchoolClass.id.in_(class_ids), SchoolClass.school_id == school_id
                )
            )
        }
        if len(targets) != len(class_ids):
            raise _not_found("Class")

    skipped: list[SkippedOut] = []
    plans: list[_Plan] = []
    for item in data.items:
        student = students[item.student_id]
        found = from_by_student.get(student.id)
        if found is None or student.status != StudentStatus.ACTIVE:
            skipped.append(
                SkippedOut(student_id=student.id, reason="not an active student in the from year")
            )
            continue
        if item.action in CONTINUING and student.id in enrolled_next:
            skipped.append(SkippedOut(student_id=student.id, reason="already enrolled"))
            continue
        from_enrollment, from_class = found
        plans.append(
            _Plan(
                item=item,
                student=student,
                from_enrollment=from_enrollment,
                from_class=from_class,
                target=_target_class(item, student, from_class, targets, actor),
            )
        )

    try:
        now = utcnow()
        hours = await settings_service.get_int(db, "promotion.undo_hours", school_id=school_id)
        batch = PromotionBatch(
            school_id=school_id,
            from_year_id=frm.id,
            to_year_id=to.id,
            created_by=actor.id,
            undo_until=now + timedelta(hours=hours),
            carry_over=data.carry_over,
        )
        db.add(batch)
        await db.flush()

        # Balances are read (and locked) before any change, so the carried amounts are exact.
        continuing_ids = [p.student.id for p in plans if p.item.action in CONTINUING]
        balances = (
            await fees_service.open_balances(db, frm.id, continuing_ids, lock=True)
            if data.carry_over
            else {}
        )

        counts: Counter[PromotionAction] = Counter()
        written: list[tuple[PromotionItem, _Plan]] = []
        for plan in plans:
            student = plan.student
            action = plan.item.action
            from_branch, from_status = student.branch_id, student.status
            to_enrollment_id: int | None = None
            if plan.target is not None:
                if plan.target.branch_id != student.branch_id:
                    student.branch_id = plan.target.branch_id
                to_enrollment_id = await students_service.enroll_for_year(
                    db,
                    student,
                    EnrollmentIn(
                        academic_year_id=to.id,
                        class_id=plan.target.id,
                        section_id=plan.item.to_section_id,
                    ),
                )
            student.status = _STATUS_FOR[action]
            row = PromotionItem(
                batch_id=batch.id,
                school_id=school_id,
                student_id=student.id,
                action=action,
                from_enrollment_id=plan.from_enrollment.id,
                to_enrollment_id=to_enrollment_id,
                from_branch_id=from_branch,
                to_branch_id=student.branch_id,
                from_status=from_status,
                to_status=student.status,
                carried_paise=0,
            )
            db.add(row)
            counts[action] += 1
            written.append((row, plan))
            await audit.record(
                db,
                actor,
                "promotion.item",
                "student",
                student.id,
                detail={"action": action.value, "moved_branch": from_branch != student.branch_id},
                school_id=school_id,
                branch_id=student.branch_id,
            )
        await db.flush()

        carried_invoices = 0
        carried_paise = 0
        if data.carry_over:
            carried_invoices, carried_paise = await _carry_over(
                db, actor, school_id, frm, to, data.due_date, written, balances
            )

        batch.promoted = counts[PromotionAction.PROMOTED]
        batch.detained = counts[PromotionAction.DETAINED]
        batch.left = counts[PromotionAction.LEFT]
        batch.passed_out = counts[PromotionAction.PASSED_OUT]
        batch.transferred = counts[PromotionAction.TRANSFERRED]
        batch.carried_invoices = carried_invoices
        batch.carried_paise = carried_paise
        await audit.record(
            db,
            actor,
            "promotion.applied",
            "promotion_batch",
            batch.id,
            detail={
                "from_year_id": frm.id,
                "to_year_id": to.id,
                "items": len(written),
                "skipped": len(skipped),
                "carry_over": data.carry_over,
                "carried_invoices": carried_invoices,
                "carried_paise": carried_paise,
            },
            school_id=school_id,
        )
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise _conflict(
            "Could not complete the promotion, please try again", "promotion_conflict"
        ) from None
    except Exception:
        await db.rollback()
        raise
    return _batch_out(batch, skipped)


async def _carry_over(
    db: AsyncSession,
    actor: User,
    school_id: int,
    frm: AcademicYear,
    to: AcademicYear,
    due_date: Any,
    written: list[tuple[PromotionItem, _Plan]],
    balances: dict[int, list[tuple[int, int]]],
) -> tuple[int, int]:
    """One carry-over invoice per continuing student who still owes money on the source year.
    Returns (invoices created, paise carried)."""
    carry_due = due_date or to.start_date + timedelta(days=CARRY_DUE_DAYS)
    title = f"Carried over dues {frm.name}"
    continuing = [(row, plan) for row, plan in written if row.action in CONTINUING]
    owing = [
        (row, plan, balances[plan.student.id])
        for row, plan in continuing
        if balances.get(plan.student.id)
    ]
    if not owing:
        return 0, 0
    already = set(
        await db.scalars(
            select(Invoice.student_id).where(
                Invoice.academic_year_id == to.id,
                Invoice.title == title,
                Invoice.student_id.in_([plan.student.id for _, plan, _ in owing]),
            )
        )
    )
    if already:
        raise _conflict("Carry-over invoices already exist for some students", "carry_over_exists")
    rows = [
        fees_service.CarryRow(
            student_id=plan.student.id,
            branch_id=plan.student.branch_id,
            academic_year_id=to.id,
            title=title,
            due_date=carry_due,
            amount_paise=sum(b for _, b in dues),
        )
        for _, plan, dues in owing
    ]
    invoice_ids = await fees_service.add_carry_over_invoices(db, actor, school_id, rows)
    amounts: dict[int, int] = {}
    for (row, _plan, dues), invoice_id, carry in zip(owing, invoice_ids, rows, strict=True):
        row.carry_invoice_id = invoice_id
        row.carried_paise = carry.amount_paise
        for original_id, balance in dues:
            amounts[original_id] = balance
    await fees_service.set_carried_forward(db, amounts)
    total = sum(r.amount_paise for r in rows)
    await audit.record(
        db,
        actor,
        "promotion.carried_over",
        "promotion_batch",
        None,
        detail={"invoices": len(rows), "amount_paise": total},
        school_id=school_id,
    )
    return len(rows), total


# ---- history ----


async def list_batches(db: AsyncSession, actor: User, page: int, page_size: int) -> list[BatchOut]:
    stmt = (
        scope_promotion_batches(select(PromotionBatch), actor)
        .order_by(PromotionBatch.id.desc())
        .limit(page_size)
        .offset((page - 1) * page_size)
    )
    return [_batch_out(b, []) for b in await db.scalars(stmt)]


async def _scoped_batch(db: AsyncSession, actor: User, batch_id: int) -> PromotionBatch:
    batch: PromotionBatch | None = await db.scalar(
        scope_promotion_batches(select(PromotionBatch), actor).where(PromotionBatch.id == batch_id)
    )
    if batch is None:
        raise _not_found("Promotion batch")
    return batch


async def _batch_items(db: AsyncSession, batch_id: int) -> list[Any]:
    fe = aliased(Enrollment)
    te = aliased(Enrollment)
    fc = aliased(SchoolClass)
    tc = aliased(SchoolClass)
    rows = await db.execute(
        select(PromotionItem, Student.first_name, Student.last_name, fc.name, tc.name)
        .join(Student, Student.id == PromotionItem.student_id)
        .outerjoin(fe, fe.id == PromotionItem.from_enrollment_id)
        .outerjoin(fc, fc.id == fe.class_id)
        .outerjoin(te, te.id == PromotionItem.to_enrollment_id)
        .outerjoin(tc, tc.id == te.class_id)
        .where(PromotionItem.batch_id == batch_id)
        .order_by(PromotionItem.id)
    )
    return list(rows.all())


async def get_batch(db: AsyncSession, actor: User, batch_id: int) -> BatchDetail:
    batch = await _scoped_batch(db, actor, batch_id)
    items = await _batch_items(db, batch.id)
    if actor.role != Role.SCHOOL_OWNER:
        # Branch staff see the students who came from or went to their branch only.
        items = [r for r in items if actor.branch_id in (r[0].from_branch_id, r[0].to_branch_id)]
    out = _batch_out(batch, [])
    return BatchDetail(
        **out.model_dump(),
        items=[
            BatchItemOut(
                student_id=item.student_id,
                name=_full_name(first, last),
                action=item.action,
                from_class=from_name,
                to_class=to_name,
                carried_paise=item.carried_paise,
                from_status=item.from_status,
                to_status=item.to_status,
            )
            for item, first, last, from_name, to_name in items
        ],
    )


# ---- undo ----


async def undo(db: AsyncSession, actor: User, batch_id: int) -> BatchOut:
    batch = await _scoped_batch(db, actor, batch_id)
    if batch.undone_at is not None:
        raise _conflict("This promotion was already undone", "already_undone")
    now = utcnow()
    if now > as_utc(batch.undo_until):
        raise _conflict("The undo window for this promotion has closed", "undo_expired")
    rows = await db.scalars(
        select(PromotionItem).where(PromotionItem.batch_id == batch.id).order_by(PromotionItem.id)
    )
    items = list(rows)
    if actor.role != Role.SCHOOL_OWNER and any(
        i.from_branch_id != i.to_branch_id or actor.branch_id != i.from_branch_id for i in items
    ):
        raise _forbidden(
            "Only the school owner can undo a promotion that moved students between branches",
            "cross_branch_forbidden",
        )

    student_ids = [i.student_id for i in items]
    visible = scope_students(select(Student), actor).where(Student.id.in_(student_ids))
    students = {s.id: s for s in await db.scalars(visible)}
    if len(students) != len(set(student_ids)):
        raise _conflict("A student of this promotion is no longer visible", "undo_blocked")
    for i in items:
        s = students[i.student_id]
        if s.branch_id != i.to_branch_id or s.status != i.to_status:
            raise _conflict(
                "A student of this promotion was changed since; undo is blocked", "undo_blocked"
            )
    enrolled_ids = [i.student_id for i in items if i.to_enrollment_id is not None]
    if enrolled_ids:
        touched = await db.scalar(
            select(AttendanceRecord.id)
            .where(
                AttendanceRecord.student_id.in_(enrolled_ids),
                AttendanceRecord.academic_year_id == batch.to_year_id,
            )
            .limit(1)
        )
        if touched is not None:
            raise _conflict(
                "Attendance has been marked for a promoted student; undo is blocked", "undo_blocked"
            )
    carry_ids = [i.carry_invoice_id for i in items if i.carry_invoice_id is not None]
    # Read before the links are cleared below: the students whose balance moved to next year.
    carried_students = [i.student_id for i in items if i.carry_invoice_id is not None]
    if carry_ids:
        paid = await db.scalar(select(Payment.id).where(Payment.invoice_id.in_(carry_ids)).limit(1))
        if paid is not None:
            raise _conflict("A carry-over invoice has payments; undo is blocked", "undo_blocked")

    try:
        for i in items:
            s = students[i.student_id]
            s.branch_id = i.from_branch_id
            s.status = i.from_status
        enrollment_ids = [i.to_enrollment_id for i in items if i.to_enrollment_id is not None]
        await db.execute(
            update(PromotionItem)
            .where(PromotionItem.batch_id == batch.id)
            .values(to_enrollment_id=None, carry_invoice_id=None)
        )
        if enrollment_ids:
            await db.execute(delete(Enrollment).where(Enrollment.id.in_(enrollment_ids)))
        if carry_ids:
            originals = list(
                await db.scalars(
                    select(Invoice.id).where(
                        Invoice.student_id.in_(carried_students),
                        Invoice.academic_year_id == batch.from_year_id,
                        Invoice.carried_forward_paise > 0,
                    )
                )
            )
            await fees_service.remove_invoices(db, carry_ids)
            await fees_service.release_carried_forward(db, originals)
        batch.undone_at = now
        batch.undone_by = actor.id
        await audit.record(
            db,
            actor,
            "promotion.undone",
            "promotion_batch",
            batch.id,
            detail={"items": len(items), "carried_invoices": len(carry_ids)},
            school_id=batch.school_id,
        )
        for i in items:
            await audit.record(
                db,
                actor,
                "promotion.item_undone",
                "student",
                i.student_id,
                detail={"action": i.action.value},
                school_id=batch.school_id,
                branch_id=i.from_branch_id,
            )
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise _conflict(
            "Could not undo the promotion, please try again", "promotion_conflict"
        ) from None
    except Exception:
        await db.rollback()
        raise
    return _batch_out(batch, [])
