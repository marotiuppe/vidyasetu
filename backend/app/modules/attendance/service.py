import csv
import io
from collections.abc import Iterable
from datetime import date, datetime, timedelta, timezone
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import and_, case, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.tenant import (
    scope_branches,
    scope_holidays,
    scope_students,
    scope_tenant,
    scope_users,
)
from app.modules.academics.models import AcademicYear, SchoolClass, Section
from app.modules.attendance.models import (
    AttendanceRecord,
    AttendanceStatus,
    Holiday,
    StaffAttendance,
    StaffStatus,
)
from app.modules.attendance.schemas import (
    Counts,
    DailySummary,
    DayRecord,
    HolidayCreate,
    SectionSummary,
    Sheet,
    SheetEntryIn,
    SheetStudent,
    StaffAttendanceSummary,
    StaffEntryIn,
    StaffRow,
    StaffSheet,
    StaffSummaryCounts,
    StudentAttendance,
    StudentSummary,
)
from app.modules.branches.models import Branch
from app.modules.students.models import Enrollment, Student, StudentStatus
from app.modules.users.models import Role, User

IST = timezone(timedelta(hours=5, minutes=30))  # no DST, so a fixed offset is exact
MAX_SPAN_DAYS = 366
STAFF_ROLES = (Role.MANAGEMENT, Role.HEADMASTER, Role.TEACHER, Role.ACCOUNTANT, Role.CLERK)
STAFF_SUMMARY_ROLES = {Role.SCHOOL_OWNER, Role.MANAGEMENT, Role.HEADMASTER, Role.CLERK}
SUNDAY = 6


def today() -> date:
    return datetime.now(IST).date()


def _not_found(what: str) -> HTTPException:
    return HTTPException(status.HTTP_404_NOT_FOUND, detail=f"{what} not found")


def _unprocessable(detail: str) -> HTTPException:
    return HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail=detail)


def _forbidden(detail: str = "Not allowed") -> HTTPException:
    return HTTPException(status.HTTP_403_FORBIDDEN, detail=detail)


async def _commit(db: AsyncSession, conflict: str) -> None:
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, detail=conflict) from None


# ---- working-day rules ----


class DayRules:
    """Non-working day rule for one date: Sunday, a school-wide holiday or the branch's holiday."""

    def __init__(self, day: date, holidays: Iterable[Holiday]) -> None:
        self.day = day
        self._wide: dict[int, str] = {}
        self._branch: dict[tuple[int, int], str] = {}
        for h in holidays:
            if h.branch_id is None:
                self._wide[h.school_id] = h.name
            else:
                self._branch[(h.school_id, h.branch_id)] = h.name

    def reason(self, school_id: int | None, branch_id: int | None = None) -> str | None:
        if self.day.weekday() == SUNDAY:
            return "Sunday"
        if school_id is None:
            return None
        if school_id in self._wide:
            return self._wide[school_id]
        if branch_id is not None:
            return self._branch.get((school_id, branch_id))
        return None


async def day_rules(db: AsyncSession, actor: User, day: date) -> DayRules:
    stmt = scope_holidays(select(Holiday), actor).where(Holiday.date == day)
    return DayRules(day, await db.scalars(stmt))


def _require_markable_date(day: date) -> None:
    if day > today():
        raise _unprocessable("Attendance cannot be saved for a future date")


def _require_working(reason: str | None) -> None:
    if reason is not None:
        raise _unprocessable(f"Not a working day: {reason}")


def _resolve_range(from_: date | None, to: date | None) -> tuple[date, date]:
    end = to or today()
    start = from_ or end.replace(day=1)
    if end < start:
        raise _unprocessable("'to' must not be before 'from'")
    if (end - start).days + 1 > MAX_SPAN_DAYS:
        raise _unprocessable(f"Date range is limited to {MAX_SPAN_DAYS} days")
    return start, end


def _percentage(score: float, marked: int) -> float | None:
    return round(score / marked * 100, 1) if marked else None


# ---- student attendance ----


async def _get_section(
    db: AsyncSession, actor: User, section_id: int
) -> tuple[Section, SchoolClass]:
    stmt = scope_tenant(
        select(Section, SchoolClass).join(SchoolClass, SchoolClass.id == Section.class_id),
        Section,
        actor,
    ).where(Section.id == section_id)
    row = (await db.execute(stmt)).first()
    if row is None:
        raise _not_found("Section")
    return row[0], row[1]


async def _year_covering(db: AsyncSession, school_id: int, day: date) -> AcademicYear:
    year = await db.scalar(
        select(AcademicYear)
        .where(
            AcademicYear.school_id == school_id,
            AcademicYear.start_date <= day,
            AcademicYear.end_date >= day,
        )
        .order_by(AcademicYear.is_current.desc(), AcademicYear.start_date.desc())
        .limit(1)
    )
    if year is None:
        raise _unprocessable("No academic year covers this date")
    return year


async def _roster(
    db: AsyncSession, actor: User, section_id: int, year_id: int
) -> list[tuple[Student, int | None]]:
    stmt = scope_students(
        select(Student, Enrollment.roll_no).join(Enrollment, Enrollment.student_id == Student.id),
        actor,
    ).where(
        Enrollment.section_id == section_id,
        Enrollment.academic_year_id == year_id,
        Student.status == StudentStatus.ACTIVE,
    )
    stmt = stmt.order_by(
        Enrollment.roll_no.is_(None),
        Enrollment.roll_no,
        Student.first_name,
        Student.last_name,
        Student.id,
    )
    return [(r[0], r[1]) for r in (await db.execute(stmt)).all()]


async def _records_on(
    db: AsyncSession, student_ids: list[int], day: date
) -> dict[int, AttendanceRecord]:
    if not student_ids:
        return {}
    rows = await db.scalars(
        select(AttendanceRecord).where(
            AttendanceRecord.student_id.in_(student_ids), AttendanceRecord.date == day
        )
    )
    return {r.student_id: r for r in rows}


def _counts(total: int, present: int, absent: int, leave: int) -> Counts:
    return Counts(
        total=total,
        present=present,
        absent=absent,
        leave=leave,
        unmarked=total - present - absent - leave,
    )


async def _build_sheet(
    db: AsyncSession,
    actor: User,
    section: Section,
    school_class: SchoolClass,
    day: date,
    year: AcademicYear,
    reason: str | None,
    roster: list[tuple[Student, int | None]] | None = None,
) -> Sheet:
    roster = roster if roster is not None else await _roster(db, actor, section.id, year.id)
    records = await _records_on(db, [s.id for s, _ in roster], day)
    students: list[SheetStudent] = []
    tally = {m.value: 0 for m in AttendanceStatus}
    for s, roll_no in roster:
        rec = records.get(s.id)
        if rec is not None:
            tally[rec.status.value] += 1
        students.append(
            SheetStudent(
                student_id=s.id,
                admission_no=s.admission_no,
                full_name=f"{s.first_name} {s.last_name}".strip(),
                roll_no=roll_no,
                status=rec.status.value if rec else None,
                remark=rec.remark if rec else None,
            )
        )
    return Sheet(
        section_id=section.id,
        section_name=section.name,
        class_id=school_class.id,
        class_name=school_class.name,
        branch_id=section.branch_id,
        date=day,
        academic_year_id=year.id,
        is_working_day=reason is None,
        non_working_reason=reason,
        students=students,
        summary=_counts(len(students), tally["present"], tally["absent"], tally["leave"]),
    )


async def get_sheet(db: AsyncSession, actor: User, section_id: int, day: date) -> Sheet:
    section, school_class = await _get_section(db, actor, section_id)
    year = await _year_covering(db, section.school_id, day)
    rules = await day_rules(db, actor, day)
    reason = rules.reason(section.school_id, section.branch_id)
    return await _build_sheet(db, actor, section, school_class, day, year, reason)


async def save_sheet(
    db: AsyncSession, actor: User, section_id: int, day: date, entries: list[SheetEntryIn]
) -> Sheet:
    section, school_class = await _get_section(db, actor, section_id)
    _require_markable_date(day)
    rules = await day_rules(db, actor, day)
    _require_working(rules.reason(section.school_id, section.branch_id))
    year = await _year_covering(db, section.school_id, day)

    roster = await _roster(db, actor, section.id, year.id)
    in_roster = {s.id for s, _ in roster}
    seen: set[int] = set()
    for e in entries:
        if e.student_id not in in_roster:
            raise _unprocessable(f"Student {e.student_id} is not in this section's roster")
        if e.student_id in seen:
            raise _unprocessable(f"Student {e.student_id} appears more than once")
        seen.add(e.student_id)

    existing = await _records_on(db, list(seen), day)
    for e in entries:
        rec = existing.get(e.student_id)
        if rec is None:
            db.add(
                AttendanceRecord(
                    school_id=section.school_id,
                    branch_id=section.branch_id,
                    student_id=e.student_id,
                    academic_year_id=year.id,
                    class_id=section.class_id,
                    section_id=section.id,
                    date=day,
                    status=e.status,
                    remark=e.remark,
                    marked_by=actor.id,
                )
            )
        elif (rec.status, rec.remark, rec.section_id) != (e.status, e.remark, section.id):
            rec.status = e.status
            rec.remark = e.remark
            rec.section_id = section.id
            rec.class_id = section.class_id
            rec.academic_year_id = year.id
            rec.updated_by = actor.id
    await _commit(db, "Attendance was changed by someone else; reload and retry")
    return await _build_sheet(db, actor, section, school_class, day, year, None, roster)


async def daily_summary(
    db: AsyncSession, actor: User, day: date, branch_id: int | None
) -> DailySummary:
    if branch_id is not None:
        branch = await db.scalar(
            scope_branches(select(Branch), actor).where(Branch.id == branch_id)
        )
        if branch is None:
            raise _not_found("Branch")
    sec_stmt = scope_tenant(
        select(Section, SchoolClass).join(SchoolClass, SchoolClass.id == Section.class_id),
        Section,
        actor,
    )
    if branch_id is not None:
        sec_stmt = sec_stmt.where(Section.branch_id == branch_id)
    sections = (
        await db.execute(sec_stmt.order_by(Section.branch_id, SchoolClass.level, Section.name))
    ).all()

    def _n(s: AttendanceStatus) -> Any:
        return func.coalesce(func.sum(case((AttendanceRecord.status == s, 1), else_=0)), 0)

    stats: dict[int, tuple[int, int, int, int]] = {}
    if sections:
        agg = scope_students(
            select(
                Enrollment.section_id,
                func.count(Enrollment.id),
                _n(AttendanceStatus.PRESENT),
                _n(AttendanceStatus.ABSENT),
                _n(AttendanceStatus.LEAVE),
            )
            .select_from(Enrollment)
            .join(Student, Student.id == Enrollment.student_id)
            .join(
                AcademicYear,
                and_(
                    AcademicYear.id == Enrollment.academic_year_id,
                    AcademicYear.start_date <= day,
                    AcademicYear.end_date >= day,
                ),
            )
            .outerjoin(
                AttendanceRecord,
                and_(AttendanceRecord.student_id == Student.id, AttendanceRecord.date == day),
            ),
            actor,
        )
        agg = agg.where(
            Student.status == StudentStatus.ACTIVE,
            Enrollment.section_id.in_([r[0].id for r in sections]),
        ).group_by(Enrollment.section_id)
        for sid, total, p, a, lv in (await db.execute(agg)).all():
            stats[sid] = (total, int(p), int(a), int(lv))

    rules = await day_rules(db, actor, day)
    out: list[SectionSummary] = []
    sums = [0, 0, 0, 0]
    for section, school_class in sections:
        total, p, a, lv = stats.get(section.id, (0, 0, 0, 0))
        for i, v in enumerate((total, p, a, lv)):
            sums[i] += v
        out.append(
            SectionSummary(
                **_counts(total, p, a, lv).model_dump(),
                branch_id=section.branch_id,
                class_id=school_class.id,
                class_name=school_class.name,
                section_id=section.id,
                section_name=section.name,
                is_working_day=rules.reason(section.school_id, section.branch_id) is None,
            )
        )
    top = rules.reason(actor.school_id)
    return DailySummary(
        date=day,
        is_working_day=top is None,
        non_working_reason=top,
        sections=out,
        totals=_counts(sums[0], sums[1], sums[2], sums[3]),
    )


async def student_attendance(
    db: AsyncSession, actor: User, student_id: int, from_: date | None, to: date | None
) -> StudentAttendance:
    found = await db.scalar(
        scope_students(select(Student.id), actor).where(Student.id == student_id)
    )
    if found is None:
        raise _not_found("Student")
    start, end = _resolve_range(from_, to)
    rows = await db.scalars(
        select(AttendanceRecord)
        .where(
            AttendanceRecord.student_id == student_id,
            AttendanceRecord.date >= start,
            AttendanceRecord.date <= end,
        )
        .order_by(AttendanceRecord.date)
    )
    records = [DayRecord(date=r.date, status=r.status.value, remark=r.remark) for r in rows]
    n = {m.value: sum(1 for r in records if r.status == m.value) for m in AttendanceStatus}
    marked = len(records)
    return StudentAttendance(
        student_id=student_id,
        from_=start,
        to=end,
        records=records,
        summary=StudentSummary(
            present=n["present"],
            absent=n["absent"],
            leave=n["leave"],
            marked_days=marked,
            percentage=_percentage(n["present"], marked),
        ),
    )


def _csv_cell(value: Any) -> str:
    """Neutralise spreadsheet formula injection."""
    text = "" if value is None else str(value)
    if text and text[0] in ("=", "+", "-", "@", "\t", "\r"):
        return "'" + text
    return text


async def export_csv(
    db: AsyncSession, actor: User, section_id: int, from_: date | None, to: date | None
) -> tuple[str, str]:
    section, school_class = await _get_section(db, actor, section_id)
    start, end = _resolve_range(from_, to)
    stmt = scope_students(
        select(AttendanceRecord, Student).join(Student, Student.id == AttendanceRecord.student_id),
        actor,
    ).where(
        AttendanceRecord.section_id == section.id,
        AttendanceRecord.date >= start,
        AttendanceRecord.date <= end,
    )
    rows = (
        await db.execute(stmt.order_by(AttendanceRecord.date, Student.admission_no, Student.id))
    ).all()
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\r\n")
    writer.writerow(["date", "admission_no", "student", "class", "section", "status", "remark"])
    for rec, s in rows:
        writer.writerow(
            _csv_cell(v)
            for v in (
                rec.date.isoformat(),
                s.admission_no,
                f"{s.first_name} {s.last_name}".strip(),
                school_class.name,
                section.name,
                rec.status.value,
                rec.remark,
            )
        )
    return buf.getvalue(), f"attendance_{section.id}_{start.isoformat()}_{end.isoformat()}.csv"


# ---- staff attendance ----


async def _staff_users(db: AsyncSession, actor: User, branch_id: int | None) -> list[User]:
    if branch_id is not None:
        branch = await db.scalar(
            scope_branches(select(Branch), actor).where(Branch.id == branch_id)
        )
        if branch is None:
            raise _not_found("Branch")
    stmt = scope_users(select(User), actor).where(
        User.role.in_(STAFF_ROLES), User.is_active.is_(True)
    )
    if branch_id is not None:
        stmt = stmt.where(User.branch_id == branch_id)
    return list(await db.scalars(stmt.order_by(User.branch_id, User.full_name, User.id)))


async def _staff_records(
    db: AsyncSession, user_ids: list[int], day: date
) -> dict[int, StaffAttendance]:
    if not user_ids:
        return {}
    rows = await db.scalars(
        select(StaffAttendance).where(
            StaffAttendance.user_id.in_(user_ids), StaffAttendance.date == day
        )
    )
    return {r.user_id: r for r in rows}


async def _staff_sheet(
    db: AsyncSession, actor: User, day: date, users: list[User], rules: DayRules
) -> StaffSheet:
    records = await _staff_records(db, [u.id for u in users], day)
    top = rules.reason(actor.school_id)
    return StaffSheet(
        date=day,
        is_working_day=top is None,
        non_working_reason=top,
        staff=[
            StaffRow(
                user_id=u.id,
                full_name=u.full_name,
                role=u.role.value,
                branch_id=u.branch_id,
                status=records[u.id].status.value if u.id in records else None,
                remark=records[u.id].remark if u.id in records else None,
            )
            for u in users
        ],
    )


async def get_staff_sheet(
    db: AsyncSession, actor: User, day: date, branch_id: int | None
) -> StaffSheet:
    users = await _staff_users(db, actor, branch_id)
    return await _staff_sheet(db, actor, day, users, await day_rules(db, actor, day))


async def save_staff_sheet(
    db: AsyncSession, actor: User, day: date, branch_id: int | None, entries: list[StaffEntryIn]
) -> StaffSheet:
    users = await _staff_users(db, actor, branch_id)
    _require_markable_date(day)
    rules = await day_rules(db, actor, day)
    _require_working(rules.reason(actor.school_id))
    by_id = {u.id: u for u in users}
    seen: set[int] = set()
    for e in entries:
        user = by_id.get(e.user_id)
        if user is None:
            raise _unprocessable(f"User {e.user_id} is not a staff member in scope")
        if e.user_id in seen:
            raise _unprocessable(f"User {e.user_id} appears more than once")
        seen.add(e.user_id)
        _require_working(rules.reason(user.school_id, user.branch_id))

    existing = await _staff_records(db, list(seen), day)
    for e in entries:
        user = by_id[e.user_id]
        rec = existing.get(e.user_id)
        if rec is None:
            if user.school_id is None or user.branch_id is None:
                raise _unprocessable(f"User {user.id} has no branch")
            db.add(
                StaffAttendance(
                    school_id=user.school_id,
                    branch_id=user.branch_id,
                    user_id=user.id,
                    date=day,
                    status=e.status,
                    remark=e.remark,
                    marked_by=actor.id,
                )
            )
        elif (rec.status, rec.remark) != (e.status, e.remark):
            rec.status = e.status
            rec.remark = e.remark
            rec.marked_by = actor.id
    await _commit(db, "Attendance was changed by someone else; reload and retry")
    return await _staff_sheet(db, actor, day, users, rules)


async def staff_summary(
    db: AsyncSession, actor: User, user_id: int, from_: date | None, to: date | None
) -> StaffAttendanceSummary:
    if user_id != actor.id:
        if actor.role not in STAFF_SUMMARY_ROLES:
            raise _forbidden()
        target = await db.scalar(
            scope_users(select(User.id), actor).where(
                User.id == user_id, User.role.in_(STAFF_ROLES)
            )
        )
        if target is None:
            raise _not_found("Staff member")
    start, end = _resolve_range(from_, to)
    rows = await db.scalars(
        select(StaffAttendance)
        .where(
            StaffAttendance.user_id == user_id,
            StaffAttendance.date >= start,
            StaffAttendance.date <= end,
        )
        .order_by(StaffAttendance.date)
    )
    records = [DayRecord(date=r.date, status=r.status.value, remark=r.remark) for r in rows]
    n = {m.value: sum(1 for r in records if r.status == m.value) for m in StaffStatus}
    marked = len(records)
    return StaffAttendanceSummary(
        user_id=user_id,
        from_=start,
        to=end,
        records=records,
        summary=StaffSummaryCounts(
            present=n["present"],
            absent=n["absent"],
            leave=n["leave"],
            half_day=n["half_day"],
            marked_days=marked,
            percentage=_percentage(n["present"] + 0.5 * n["half_day"], marked),
        ),
    )


# ---- holidays ----


async def _branch_in_scope(db: AsyncSession, actor: User, branch_id: int) -> None:
    found = await db.scalar(
        scope_branches(select(Branch.id), actor).where(Branch.id == branch_id)
    )
    if found is None:
        raise _not_found("Branch")


async def list_holidays(
    db: AsyncSession, actor: User, from_: date | None, to: date | None, branch_id: int | None
) -> list[Holiday]:
    default_from, default_to = today(), today() + timedelta(days=365)
    if actor.school_id is not None:
        year = await db.scalar(
            select(AcademicYear).where(
                AcademicYear.school_id == actor.school_id, AcademicYear.is_current.is_(True)
            )
        )
        if year is not None:
            default_from, default_to = year.start_date, year.end_date
    start, end = from_ or default_from, to or default_to
    if end < start:
        raise _unprocessable("'to' must not be before 'from'")
    stmt = scope_holidays(select(Holiday), actor).where(Holiday.date >= start, Holiday.date <= end)
    if branch_id is not None:
        await _branch_in_scope(db, actor, branch_id)
        stmt = stmt.where(or_(Holiday.branch_id.is_(None), Holiday.branch_id == branch_id))
    return list(await db.scalars(stmt.order_by(Holiday.date, Holiday.branch_id, Holiday.id)))


async def create_holiday(db: AsyncSession, actor: User, data: HolidayCreate) -> Holiday:
    if actor.school_id is None:
        raise _forbidden()
    if data.branch_id is None:
        if actor.role != Role.SCHOOL_OWNER:
            raise _forbidden("Only the school owner can add school-wide holidays")
    else:
        await _branch_in_scope(db, actor, data.branch_id)
    dup = select(Holiday.id).where(Holiday.school_id == actor.school_id, Holiday.date == data.date)
    dup = dup.where(
        Holiday.branch_id.is_(None)
        if data.branch_id is None
        else Holiday.branch_id == data.branch_id
    )
    if await db.scalar(dup) is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT, detail="A holiday already exists for this date"
        )
    holiday = Holiday(
        school_id=actor.school_id,
        branch_id=data.branch_id,
        date=data.date,
        name=data.name,
        created_by=actor.id,
    )
    db.add(holiday)
    await _commit(db, "A holiday already exists for this date")
    return holiday


async def delete_holiday(db: AsyncSession, actor: User, holiday_id: int) -> None:
    holiday = await db.scalar(
        scope_holidays(select(Holiday), actor).where(Holiday.id == holiday_id)
    )
    if holiday is None:
        raise _not_found("Holiday")
    if holiday.branch_id is None and actor.role != Role.SCHOOL_OWNER:
        raise _forbidden("Only the school owner can remove school-wide holidays")
    await db.delete(holiday)
    await db.commit()
