import csv
import io
import re
import secrets
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from typing import Any

from fastapi import HTTPException, status
from pydantic import ValidationError
from sqlalchemy import and_, exists, func, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.core.errors import ApiError, IdentityInUse
from app.core.password_policy import enforce_password, password_problem
from app.core.security import hash_password
from app.core.tenant import scope_branches, scope_students
from app.modules.academics.models import AcademicYear, SchoolClass, Section
from app.modules.audit import service as audit
from app.modules.branches.models import Branch
from app.modules.consent import service as consent_service
from app.modules.settings import service as settings_service
from app.modules.students.models import (
    Enrollment,
    Guardian,
    GuardianRelation,
    Student,
    StudentStatus,
)
from app.modules.students.schemas import (
    CredentialOut,
    EnrollmentIn,
    EnrollmentOut,
    GuardianCreate,
    GuardianOut,
    GuardianUpdate,
    ImportRequest,
    ImportResult,
    ImportRow,
    ImportRowError,
    LoginCreate,
    NewGuardian,
    ParentChild,
    ParentOut,
    PrimaryGuardianOut,
    StudentCreate,
    StudentCreated,
    StudentDetail,
    StudentOut,
    StudentPage,
    StudentUpdate,
)
from app.modules.users.identity import normalize_phone
from app.modules.users.models import Role, User
from app.modules.users.service import (
    IDENTITY_TAKEN_CODE,
    derive_unique_username,
    ensure_identity_available,
)

MAX_ROLL = 999
_GENERATED = ("admission_no", "admission_date")
CSV_COLUMNS = [
    "admission_no",
    "first_name",
    "last_name",
    "gender",
    "date_of_birth",
    "admission_date",
    "status",
    "class",
    "section",
    "roll_no",
    "guardian_name",
    "guardian_phone",
    "guardian_relation",
    "address",
]


def _not_found(what: str) -> HTTPException:
    return HTTPException(status.HTTP_404_NOT_FOUND, detail=f"{what} not found")


def _conflict(detail: str) -> HTTPException:
    return HTTPException(status.HTTP_409_CONFLICT, detail=detail)


def _unprocessable(detail: str) -> HTTPException:
    return HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail=detail)


@dataclass
class StudentFilters:
    branch_id: int | None = None
    class_id: int | None = None
    section_id: int | None = None
    academic_year_id: int | None = None
    status: StudentStatus | None = None
    q: str | None = None


# ---- output building (batched, no N+1) ----


def _guardian_out(g: Guardian) -> GuardianOut:
    return GuardianOut(
        id=g.id,
        student_id=g.student_id,
        full_name=g.full_name,
        relation=g.relation,
        phone=g.phone,
        email=g.email,
        is_primary=g.is_primary,
        user_id=g.user_id,
        has_login=g.user_id is not None,
    )


async def _enrollments_by_student(
    db: AsyncSession, student_ids: list[int], current_only: bool
) -> dict[int, list[EnrollmentOut]]:
    """Enrolments (newest academic year first) with year/class/section names, in one query."""
    stmt = (
        select(Enrollment, AcademicYear.name, SchoolClass.name, Section.name)
        .join(AcademicYear, AcademicYear.id == Enrollment.academic_year_id)
        .join(SchoolClass, SchoolClass.id == Enrollment.class_id)
        .outerjoin(Section, Section.id == Enrollment.section_id)
        .where(Enrollment.student_id.in_(student_ids))
        .order_by(AcademicYear.start_date.desc(), Enrollment.id.desc())
    )
    if current_only:
        stmt = stmt.where(AcademicYear.is_current)
    out: dict[int, list[EnrollmentOut]] = {}
    for enr, year_name, class_name, sec_name in (await db.execute(stmt)).all():
        out.setdefault(enr.student_id, []).append(
            EnrollmentOut(
                id=enr.id,
                student_id=enr.student_id,
                academic_year_id=enr.academic_year_id,
                academic_year_name=year_name,
                class_id=enr.class_id,
                class_name=class_name,
                section_id=enr.section_id,
                section_name=sec_name,
                roll_no=enr.roll_no,
            )
        )
    return out


async def _guardians_by_student(
    db: AsyncSession, student_ids: list[int], primary_only: bool
) -> dict[int, list[Guardian]]:
    stmt = select(Guardian).where(Guardian.student_id.in_(student_ids))
    if primary_only:
        stmt = stmt.where(Guardian.is_primary)
    out: dict[int, list[Guardian]] = {}
    for g in await db.scalars(stmt.order_by(Guardian.is_primary.desc(), Guardian.id)):
        out.setdefault(g.student_id, []).append(g)
    return out


def _base_fields(
    s: Student, current: EnrollmentOut | None, guardians: list[Guardian]
) -> dict[str, Any]:
    primary = next((g for g in guardians if g.is_primary), None)
    return {
        "id": s.id,
        "school_id": s.school_id,
        "branch_id": s.branch_id,
        "admission_no": s.admission_no,
        "first_name": s.first_name,
        "last_name": s.last_name,
        "full_name": f"{s.first_name} {s.last_name}".strip(),
        "gender": s.gender,
        "date_of_birth": s.date_of_birth,
        "admission_date": s.admission_date,
        "status": s.status,
        "user_id": s.user_id,
        "current_enrollment": current,
        "primary_guardian": PrimaryGuardianOut(
            full_name=primary.full_name, phone=primary.phone, relation=primary.relation
        )
        if primary
        else None,
    }


async def _build_list(db: AsyncSession, students: list[Student]) -> list[StudentOut]:
    if not students:
        return []
    ids = [s.id for s in students]
    enrollments = await _enrollments_by_student(db, ids, current_only=True)
    guardians = await _guardians_by_student(db, ids, primary_only=True)
    return [
        StudentOut(
            **_base_fields(
                s, next(iter(enrollments.get(s.id, [])), None), guardians.get(s.id, [])
            )
        )
        for s in students
    ]


async def _build_detail(db: AsyncSession, s: Student) -> StudentDetail:
    all_enrollments = (await _enrollments_by_student(db, [s.id], current_only=False)).get(s.id, [])
    guardians = (await _guardians_by_student(db, [s.id], primary_only=False)).get(s.id, [])
    current_ids = set(
        await db.scalars(
            select(Enrollment.id)
            .join(AcademicYear, AcademicYear.id == Enrollment.academic_year_id)
            .where(Enrollment.student_id == s.id, AcademicYear.is_current)
        )
    )
    current = next((e for e in all_enrollments if e.id in current_ids), None)
    return StudentDetail(
        **_base_fields(s, current, guardians),
        address=s.address,
        previous_school=s.previous_school,
        guardians=[_guardian_out(g) for g in guardians],
        enrollments=all_enrollments,
        consent_status=await consent_service.current_status(db, s.id),
    )


# ---- lookups ----


async def _get_student(db: AsyncSession, actor: User, student_id: int) -> Student:
    student: Student | None = await db.scalar(
        scope_students(select(Student), actor).where(Student.id == student_id)
    )
    if student is None:
        raise _not_found("Student")
    return student


async def _get_guardian(
    db: AsyncSession, actor: User, guardian_id: int
) -> tuple[Guardian, Student]:
    guardian = await db.scalar(
        select(Guardian).where(
            Guardian.id == guardian_id,
            Guardian.student_id.in_(scope_students(select(Student.id), actor)),
        )
    )
    if guardian is None:
        raise _not_found("Guardian")
    student = await db.get(Student, guardian.student_id)
    if student is None:  # FK guarantees it
        raise _not_found("Student")
    return guardian, student


async def _resolve_branch(db: AsyncSession, actor: User, branch_id: int | None) -> Branch:
    wanted = actor.branch_id if actor.branch_id is not None else branch_id
    if wanted is None:
        raise _unprocessable("branch_id required")
    branch: Branch | None = await db.scalar(
        scope_branches(select(Branch), actor).where(Branch.id == wanted)
    )
    if branch is None:
        raise _not_found("Branch")
    return branch


# ---- list / export ----


def _filtered(actor: User, f: StudentFilters) -> tuple[Any, Any, Any, Any]:
    """Scoped, filtered and ordered student query plus the aliased enrolment joins."""
    enr = aliased(Enrollment)
    cls = aliased(SchoolClass)
    sec = aliased(Section)
    if f.academic_year_id is not None:
        year_cond = enr.academic_year_id == f.academic_year_id
    else:
        year_cond = enr.academic_year_id.in_(select(AcademicYear.id).where(AcademicYear.is_current))
    stmt = (
        scope_students(select(Student), actor)
        .select_from(Student)
        .outerjoin(enr, and_(enr.student_id == Student.id, year_cond))
        .outerjoin(cls, cls.id == enr.class_id)
        .outerjoin(sec, sec.id == enr.section_id)
    )
    if f.branch_id is not None:
        stmt = stmt.where(Student.branch_id == f.branch_id)
    if f.status is not None:
        stmt = stmt.where(Student.status == f.status)
    if f.class_id is not None:
        stmt = stmt.where(enr.class_id == f.class_id)
    if f.section_id is not None:
        stmt = stmt.where(enr.section_id == f.section_id)
    term = (f.q or "").strip().lower()
    if term:
        stmt = stmt.where(
            or_(
                func.lower(Student.first_name).contains(term, autoescape=True),
                func.lower(Student.last_name).contains(term, autoescape=True),
                func.lower(Student.first_name + " " + Student.last_name).contains(
                    term, autoescape=True
                ),
                func.lower(Student.admission_no).contains(term, autoescape=True),
                exists().where(
                    Guardian.student_id == Student.id,
                    or_(
                        func.lower(Guardian.full_name).contains(term, autoescape=True),
                        Guardian.phone.contains(term, autoescape=True),
                    ),
                ),
            )
        )
    stmt = stmt.order_by(
        cls.level.asc().nulls_last(),
        sec.name.asc().nulls_last(),
        enr.roll_no.asc().nulls_last(),
        Student.first_name,
        Student.last_name,
        Student.id,
    )
    return stmt, cls, sec, enr


async def list_students(
    db: AsyncSession, actor: User, f: StudentFilters, page: int, page_size: int
) -> StudentPage:
    stmt, *_ = _filtered(actor, f)
    total = await db.scalar(
        select(func.count()).select_from(
            stmt.with_only_columns(Student.id).order_by(None).subquery()
        )
    )
    rows = await db.scalars(stmt.offset((page - 1) * page_size).limit(page_size))
    items = await _build_list(db, list(rows))
    return StudentPage(items=items, total=total or 0, page=page, page_size=page_size)


def _csv_cell(value: Any) -> str:
    """Neutralise spreadsheet formula injection."""
    text = "" if value is None else str(value)
    if text and text[0] in ("=", "+", "-", "@", "\t", "\r"):
        return "'" + text
    return text


async def export_csv(db: AsyncSession, actor: User, f: StudentFilters) -> str:
    stmt, cls, sec, enr = _filtered(actor, f)
    rows = (await db.execute(stmt.add_columns(cls.name, sec.name, enr.roll_no))).all()
    guardians = await _guardians_by_student(db, [r[0].id for r in rows], primary_only=True)
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\r\n")
    writer.writerow(CSV_COLUMNS)
    for s, class_name, sec_name, roll_no in rows:
        g = next(iter(guardians.get(s.id, [])), None)
        writer.writerow(
            _csv_cell(v)
            for v in (
                s.admission_no,
                s.first_name,
                s.last_name,
                s.gender.value,
                s.date_of_birth.isoformat(),
                s.admission_date.isoformat(),
                s.status.value,
                class_name,
                sec_name,
                roll_no,
                g.full_name if g else None,
                g.phone if g else None,
                g.relation.value if g else None,
                s.address,
            )
        )
    await audit.record(
        db, actor, "student.exported", "student", None,
        detail={"scope": "list", "rows": len(rows)}, commit=True,
    )
    return buf.getvalue()


_PEOPLE_WHO_VIEW_OWN = (Role.PARENT, Role.STUDENT)


async def get_student(
    db: AsyncSession, actor: User, student_id: int, *, log_view: bool = True
) -> StudentDetail:
    student = await _get_student(db, actor, student_id)
    if log_view and actor.role not in _PEOPLE_WHO_VIEW_OWN:
        # Staff reads of a student's full profile are logged (parents and students see their own).
        await audit.record(
            db, actor, "student.viewed", "student", student.id,
            school_id=student.school_id, branch_id=student.branch_id, commit=True,
        )
    return await _build_detail(db, student)


# ---- enrolment ----


async def _validate_enrollment(
    db: AsyncSession, school_id: int, branch_id: int, data: EnrollmentIn
) -> tuple[AcademicYear, SchoolClass, Section | None]:
    year = await db.scalar(
        select(AcademicYear).where(
            AcademicYear.id == data.academic_year_id, AcademicYear.school_id == school_id
        )
    )
    if year is None:
        raise _not_found("Academic year")
    school_class = await db.scalar(
        select(SchoolClass).where(
            SchoolClass.id == data.class_id,
            SchoolClass.branch_id == branch_id,
            SchoolClass.school_id == school_id,
        )
    )
    if school_class is None:
        raise _not_found("Class")
    section = None
    if data.section_id is not None:
        section = await db.scalar(
            select(Section).where(
                Section.id == data.section_id, Section.class_id == school_class.id
            )
        )
        if section is None:
            raise _unprocessable("Section does not belong to the class")
    return year, school_class, section


async def _next_roll(db: AsyncSession, section_id: int, year_id: int) -> int:
    highest = await db.scalar(
        select(func.max(Enrollment.roll_no)).where(
            Enrollment.section_id == section_id, Enrollment.academic_year_id == year_id
        )
    )
    nxt = (highest or 0) + 1
    if nxt > MAX_ROLL:
        raise _unprocessable("No free roll number in this section")
    return nxt


async def _apply_enrollment(db: AsyncSession, student: Student, data: EnrollmentIn) -> None:
    """Upsert the student's enrolment for one academic year (caller commits)."""
    year, school_class, section = await _validate_enrollment(
        db, student.school_id, student.branch_id, data
    )
    existing = await db.scalar(
        select(Enrollment).where(
            Enrollment.student_id == student.id, Enrollment.academic_year_id == year.id
        )
    )
    section_id = section.id if section else None
    roll = data.roll_no
    if section_id is not None:
        if roll is None:
            if existing and existing.section_id == section_id and existing.roll_no is not None:
                roll = existing.roll_no
            else:
                roll = await _next_roll(db, section_id, year.id)
        else:
            clash = await db.scalar(
                select(Enrollment.id).where(
                    Enrollment.section_id == section_id,
                    Enrollment.academic_year_id == year.id,
                    Enrollment.roll_no == roll,
                    Enrollment.student_id != student.id,
                )
            )
            if clash is not None:
                raise _conflict("Roll number already taken in this section")
    if existing is None:
        existing = Enrollment(
            school_id=student.school_id,
            branch_id=student.branch_id,
            student_id=student.id,
            academic_year_id=year.id,
        )
        db.add(existing)
    existing.class_id = school_class.id
    existing.section_id = section_id
    existing.roll_no = roll
    await db.flush()


async def set_enrollment(
    db: AsyncSession, actor: User, student_id: int, data: EnrollmentIn
) -> StudentDetail:
    student = await _get_student(db, actor, student_id)
    try:
        await _apply_enrollment(db, student, data)
        await audit.record(
            db, actor, "enrollment.set", "student", student.id,
            detail={
                "academic_year_id": data.academic_year_id,
                "class_id": data.class_id,
                "section_id": data.section_id,
            },
            school_id=student.school_id, branch_id=student.branch_id,
        )
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise _conflict("Roll number already taken in this section") from None
    return await _build_detail(db, student)


# ---- create / update ----


async def _next_admission_no(db: AsyncSession, school_id: int, year: int) -> str:
    """`{YYYY}-{seq:04d}` where seq is the highest existing sequence for that year, plus one."""
    pattern = re.compile(rf"^{year}-(\d+)$")
    highest = 0
    for no in await db.scalars(
        select(Student.admission_no).where(
            Student.school_id == school_id,
            Student.admission_no.startswith(f"{year}-", autoescape=True),
        )
    ):
        m = pattern.match(no)
        if m:
            highest = max(highest, int(m.group(1)))
    return f"{year}-{highest + 1:04d}"


async def _insert_student(
    db: AsyncSession,
    branch: Branch,
    fields: dict[str, Any],
    guardians: Sequence[GuardianCreate],
    enrollment: EnrollmentIn | None,
) -> tuple[Student, list[Guardian]]:
    """Insert a student, guardians and optional enrolment atomically (one savepoint).

    Returns the student and its guardian rows in the order they were given.
    """
    admission_date: date = fields["admission_date"] or date.today()
    supplied: str | None = fields["admission_no"]
    if supplied is not None and await db.scalar(
        select(Student.id).where(
            Student.school_id == branch.school_id, Student.admission_no == supplied
        )
    ):
        raise _conflict("Admission number already exists")
    primary_idx = next((i for i, g in enumerate(guardians) if g.is_primary), 0)
    for attempt in (0, 1):
        try:
            async with db.begin_nested():
                student = Student(
                    **{k: v for k, v in fields.items() if k not in _GENERATED},
                    school_id=branch.school_id,
                    branch_id=branch.id,
                    admission_date=admission_date,
                    admission_no=supplied
                    or await _next_admission_no(db, branch.school_id, admission_date.year),
                    status=StudentStatus.ACTIVE,
                )
                db.add(student)
                await db.flush()
                rows: list[Guardian] = []
                for i, g in enumerate(guardians):
                    row = Guardian(
                        school_id=branch.school_id,
                        student_id=student.id,
                        full_name=g.full_name,
                        relation=g.relation,
                        phone=g.phone,
                        email=g.email,
                        is_primary=i == primary_idx,
                    )
                    db.add(row)
                    rows.append(row)
                await db.flush()
                if enrollment is not None:
                    await _apply_enrollment(db, student, enrollment)
            return student, rows
        except IntegrityError:
            if attempt == 0 and supplied is None:
                continue  # lost a race for the generated number; regenerate once
            raise _conflict("Admission or roll number already exists, please retry") from None
    raise AssertionError("unreachable")


_PATTERN_NOTE = (
    "Password follows the pattern name+initial@DOB; the student must change it at first sign-in"
)
_LINKED_NOTE = "Existing parent login linked; its password is unchanged"
_PW_UPPER = "ABCDEFGHJKLMNPQRSTUVWXYZ"  # no I or O
_PW_LOWER = "abcdefghijkmnopqrstuvwxyz"  # no l
_PW_DIGIT = "23456789"  # no 0 or 1
_PW_SYMBOL = "@#$%&*"
_PW_ALL = _PW_UPPER + _PW_LOWER + _PW_DIGIT + _PW_SYMBOL
_PW_LENGTH = 12


def _random_password(username: str, full_name: str) -> str:
    """A 12-character random password that passes the password policy."""
    rng = secrets.SystemRandom()
    while True:
        chars = [
            secrets.choice(_PW_UPPER),
            secrets.choice(_PW_LOWER),
            secrets.choice(_PW_DIGIT),
            secrets.choice(_PW_SYMBOL),
        ]
        chars += [secrets.choice(_PW_ALL) for _ in range(_PW_LENGTH - len(chars))]
        rng.shuffle(chars)
        password = "".join(chars)
        if password_problem(password, username=username, full_name=full_name) is None:
            return password


def _first_word_stem(text: str, fallback: str) -> str:
    """Lower-case letters and digits of the first word; the fallback when no letter is left."""
    words = text.split()
    stem = re.sub(r"[^a-z0-9]", "", (words[0] if words else "").lower())
    return stem if re.search(r"[a-z]", stem) else fallback


def _first_letter(text: str) -> str:
    match = re.search(r"[a-z]", text.lower())
    return match.group(0) if match else ""


async def _free_username(db: AsyncSession, base: str) -> str:
    """`base`, or `base` plus 2, 3, ... when the username is taken."""
    candidate, n = base, 2
    while await db.scalar(select(User.id).where(User.username == candidate)) is not None:
        candidate = f"{base}{n}"
        n += 1
    return candidate


async def _free_email(db: AsyncSession, email: str | None) -> str | None:
    """The email if no account uses it, else None (the parent is created without one)."""
    if email is None:
        return None
    try:
        await ensure_identity_available(db, email=email)
    except IdentityInUse:
        return None
    return email


async def _school_parent_match(
    db: AsyncSession, school_id: int, email: str | None, raw_phone: str
) -> User | None:
    """A parent login of this school for a new guardian: matched by email, then by mobile.

    Unlike `_existing_parent`, a match in another school or of another role is ignored rather
    than refused, so a new student can still be created; the parent then gets no email or
    mobile number of its own (both are unique).
    """
    if email is not None:
        user = await db.scalar(
            select(User).where(
                User.email == email, User.school_id == school_id, User.role == Role.PARENT
            )
        )
        if user is not None:
            return user
    try:
        phone = normalize_phone(raw_phone)
    except ValueError:
        return None
    return await db.scalar(
        select(User).where(
            User.phone == phone, User.school_id == school_id, User.role == Role.PARENT
        )
    )


async def _parent_username(db: AsyncSession, full_name: str, raw_phone: str) -> str:
    """First name, last-name initial and last 4 mobile digits (a number is added on a clash)."""
    words = full_name.split()
    stem = _first_word_stem(full_name, "parent")[:40]
    initial = _first_letter(words[-1]) if len(words) > 1 else ""
    digits = re.sub(r"\D", "", raw_phone)
    base = f"{stem}{initial}{digits[-4:]}".ljust(3, "0")
    return await _free_username(db, base)


def _linked_credential(parent: User) -> CredentialOut:
    return CredentialOut(
        role="parent",
        full_name=parent.full_name,
        username=parent.username,
        temporary_password=None,
        linked_existing=True,
        note=_LINKED_NOTE,
    )


async def _guardian_login(
    db: AsyncSession, student: Student, guardian: Guardian, spec: NewGuardian
) -> CredentialOut:
    """Link the guardian to an existing parent login, or create a parent login for it."""
    if spec.existing_parent_user_id is not None:
        parent = await db.scalar(
            select(User).where(
                User.id == spec.existing_parent_user_id,
                User.school_id == student.school_id,
                User.role == Role.PARENT,
            )
        )
        if parent is None:
            raise _not_found("Parent")
        guardian.user_id = parent.id
        return _linked_credential(parent)
    email = str(guardian.email).lower() if guardian.email is not None else None
    parent = await _school_parent_match(db, student.school_id, email, guardian.phone)
    if parent is not None:
        guardian.user_id = parent.id
        return _linked_credential(parent)
    username = await _parent_username(db, guardian.full_name, guardian.phone)
    password = _random_password(username, guardian.full_name)
    user = User(
        school_id=student.school_id,
        branch_id=None,
        username=username,
        email=await _free_email(db, email),
        full_name=guardian.full_name,
        phone=await _parent_phone(db, guardian.phone, student.school_id),
        password_hash=hash_password(password),
        role=Role.PARENT,
        must_change_password=await settings_service.force_password_change(
            db, student.school_id
        ),
    )
    db.add(user)
    await db.flush()
    guardian.user_id = user.id
    return CredentialOut(
        role="parent",
        full_name=user.full_name,
        username=username,
        temporary_password=password,
        linked_existing=False,
        note=None,
    )


async def _student_login(db: AsyncSession, student: Student) -> CredentialOut:
    """The student's own login: username and password follow the name and date-of-birth pattern."""
    stem = _first_word_stem(student.first_name, "student")[:30]
    initial = _first_letter(student.last_name)
    dob = student.date_of_birth.strftime("%d%m%Y")
    full_name = f"{student.first_name} {student.last_name}".strip()
    username = await _free_username(db, f"{stem}{initial}{dob}")
    pattern = f"{stem}{initial}@{dob}"
    if password_problem(pattern, username=username, full_name=full_name) is None:
        password, note = pattern, _PATTERN_NOTE
    else:
        password, note = _random_password(username, full_name), None
    # The date-of-birth pattern is guessable, so it always has to be replaced at first sign-in.
    forced = password == pattern or await settings_service.force_password_change(
        db, student.school_id
    )
    user = User(
        school_id=student.school_id,
        branch_id=student.branch_id,
        username=username,
        email=None,
        full_name=full_name,
        password_hash=hash_password(password),
        role=Role.STUDENT,
        must_change_password=forced,
    )
    db.add(user)
    await db.flush()
    student.user_id = user.id
    return CredentialOut(
        role="student",
        full_name=full_name,
        username=username,
        temporary_password=password,
        linked_existing=False,
        note=note,
    )


def _logins_requested(data: StudentCreate) -> bool:
    """True when the request uses the login fields. Without them no login is created at all."""
    if "create_student_login" in data.model_fields_set:
        return True
    return any(
        bool({"create_login", "existing_parent_user_id"} & g.model_fields_set)
        for g in data.guardians
    )


async def _create_logins(
    db: AsyncSession,
    student: Student,
    guardians: list[Guardian],
    data: StudentCreate,
    requested: bool,
) -> list[CredentialOut]:
    credentials: list[CredentialOut] = []
    if data.create_student_login:
        credentials.append(await _student_login(db, student))
    primary_idx = next((i for i, g in enumerate(data.guardians) if g.is_primary), 0)
    for i, (guardian, spec) in enumerate(zip(guardians, data.guardians, strict=True)):
        if spec.existing_parent_user_id is None:
            wanted = (
                spec.create_login
                if spec.create_login is not None
                else (requested and i == primary_idx)
            )
            if not wanted:
                continue
        credentials.append(await _guardian_login(db, student, guardian, spec))
    return credentials


async def create_student(db: AsyncSession, actor: User, data: StudentCreate) -> StudentCreated:
    """Create the student, guardians, enrolment and any requested logins in one transaction."""
    branch = await _resolve_branch(db, actor, data.branch_id)
    if data.create_student_login and not await settings_service.student_logins_enabled(
        db, branch.school_id
    ):
        raise ApiError(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Student logins are switched off for this school",
            "student_logins_disabled",
        )
    fields = data.model_dump(
        exclude={"branch_id", "guardians", "enrollment", "create_student_login"}
    )
    requested = _logins_requested(data)
    try:
        student, guardians = await _insert_student(
            db, branch, fields, data.guardians, data.enrollment
        )
        credentials = await _create_logins(db, student, guardians, data, requested)
        await audit.record(
            db, actor, "student.created", "student", student.id,
            school_id=student.school_id, branch_id=student.branch_id,
            detail={"logins_created": requested},
        )
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise IdentityInUse(
            "Username, email or mobile number already in use", IDENTITY_TAKEN_CODE
        ) from None
    except Exception:
        await db.rollback()
        raise
    detail = await _build_detail(db, student)
    return StudentCreated(**detail.model_dump(), credentials=credentials)


async def _parent_children(
    db: AsyncSession, actor: User, parent_ids: list[int]
) -> dict[int, list[ParentChild]]:
    """Children of each parent that the actor may see (the actor's school and branch scope)."""
    if not parent_ids:
        return {}
    enr = aliased(Enrollment)
    cls = aliased(SchoolClass)
    year_cond = enr.academic_year_id.in_(select(AcademicYear.id).where(AcademicYear.is_current))
    stmt = (
        select(Guardian.user_id, Student.id, Student.first_name, Student.last_name, cls.name)
        .select_from(Guardian)
        .join(Student, Student.id == Guardian.student_id)
        .outerjoin(enr, and_(enr.student_id == Student.id, year_cond))
        .outerjoin(cls, cls.id == enr.class_id)
        .where(
            Guardian.user_id.in_(parent_ids),
            Student.id.in_(scope_students(select(Student.id), actor)),
        )
        .order_by(Student.first_name, Student.last_name, Student.id)
    )
    out: dict[int, list[ParentChild]] = {}
    seen: set[tuple[int, int]] = set()
    for user_id, student_id, first, last, class_name in await db.execute(stmt):
        if user_id is None or (user_id, student_id) in seen:
            continue
        seen.add((user_id, student_id))
        out.setdefault(user_id, []).append(
            ParentChild(
                student_id=student_id,
                full_name=f"{first} {last}".strip(),
                class_name=class_name,
            )
        )
    return out


async def search_parents(db: AsyncSession, actor: User, q: str, limit: int) -> list[ParentOut]:
    """Parent logins of the actor's school matching the text (name, username, email or mobile)."""
    term = q.strip().lower()
    if actor.role == Role.SUPER_ADMIN or actor.school_id is None or len(term) < 2:
        return []
    conditions = [
        func.lower(User.full_name).contains(term, autoescape=True),
        func.lower(User.username).contains(term, autoescape=True),
        func.lower(User.email).contains(term, autoescape=True),
    ]
    digits = re.sub(r"\D", "", term)
    if len(digits) >= 3:
        conditions.append(User.phone.contains(digits, autoescape=True))
    parents = list(
        await db.scalars(
            select(User)
            .where(
                User.school_id == actor.school_id,
                User.role == Role.PARENT,
                or_(*conditions),
            )
            .order_by(User.full_name, User.id)
            .limit(limit)
        )
    )
    children = await _parent_children(db, actor, [p.id for p in parents])
    return [
        ParentOut(
            id=p.id,
            full_name=p.full_name,
            username=p.username,
            phone=p.phone,
            email=p.email,
            children=children.get(p.id, []),
        )
        for p in parents
    ]


async def update_student(
    db: AsyncSession, actor: User, student_id: int, data: StudentUpdate
) -> StudentDetail:
    student = await _get_student(db, actor, student_id)
    changes = data.model_dump(exclude_unset=True)
    for field in ("first_name", "last_name", "gender", "date_of_birth", "admission_date", "status"):
        if field in changes and changes[field] is None:
            raise _unprocessable(f"{field} cannot be null")
    for field, value in changes.items():
        setattr(student, field, value)
    await audit.record(
        db, actor, "student.updated", "student", student.id,
        detail={"fields": ",".join(sorted(changes))},
        school_id=student.school_id, branch_id=student.branch_id,
    )
    await db.commit()
    return await _build_detail(db, student)


# ---- guardians ----


async def _clear_primary(db: AsyncSession, student_id: int, except_id: int | None) -> None:
    stmt = update(Guardian).where(Guardian.student_id == student_id, Guardian.is_primary)
    if except_id is not None:
        stmt = stmt.where(Guardian.id != except_id)
    await db.execute(stmt.values(is_primary=False))


async def _count_guardians(db: AsyncSession, student_id: int) -> int:
    count = await db.scalar(
        select(func.count()).select_from(Guardian).where(Guardian.student_id == student_id)
    )
    return count or 0


async def add_guardian(
    db: AsyncSession, actor: User, student_id: int, data: GuardianCreate
) -> GuardianOut:
    student = await _get_student(db, actor, student_id)
    primary = await _count_guardians(db, student.id) == 0 or bool(data.is_primary)
    if primary:
        await _clear_primary(db, student.id, None)
    guardian = Guardian(
        school_id=student.school_id,
        student_id=student.id,
        full_name=data.full_name,
        relation=data.relation,
        phone=data.phone,
        email=data.email,
        is_primary=primary,
    )
    db.add(guardian)
    await db.commit()
    return _guardian_out(guardian)


async def update_guardian(
    db: AsyncSession, actor: User, guardian_id: int, data: GuardianUpdate
) -> GuardianOut:
    guardian, _ = await _get_guardian(db, actor, guardian_id)
    changes = data.model_dump(exclude_unset=True)
    for field in ("full_name", "relation", "phone", "is_primary"):
        if field in changes and changes[field] is None:
            raise _unprocessable(f"{field} cannot be null")
    make_primary = changes.pop("is_primary", None)
    if make_primary is False and guardian.is_primary:
        raise _unprocessable(
            "A student must have a primary guardian; mark another guardian as primary"
        )
    for field, value in changes.items():
        setattr(guardian, field, value)
    if make_primary and not guardian.is_primary:
        await _clear_primary(db, guardian.student_id, guardian.id)
        guardian.is_primary = True
    await db.commit()
    return _guardian_out(guardian)


async def delete_guardian(db: AsyncSession, actor: User, guardian_id: int) -> None:
    guardian, _ = await _get_guardian(db, actor, guardian_id)
    if await _count_guardians(db, guardian.student_id) <= 1:
        raise _conflict("A student must have at least one guardian")
    was_primary = guardian.is_primary
    student_id = guardian.student_id
    await db.delete(guardian)
    await db.flush()
    if was_primary:
        heir = await db.scalar(
            select(Guardian).where(Guardian.student_id == student_id).order_by(Guardian.id).limit(1)
        )
        if heir is not None:
            heir.is_primary = True
    await db.commit()


async def _commit_login(db: AsyncSession) -> None:
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise IdentityInUse(
            "Username, email or mobile number already in use", IDENTITY_TAKEN_CODE
        ) from None


async def _login_username(db: AsyncSession, data: LoginCreate) -> str:
    """The requested username, or one derived from the email (with a suffix if taken)."""
    if data.username is not None:
        await ensure_identity_available(db, username=data.username)
        return data.username
    if data.email is not None:
        return await derive_unique_username(db, str(data.email))
    raise _unprocessable("Give a username or an email")


async def _parent_phone(db: AsyncSession, raw: str | None, school_id: int) -> str | None:
    """The guardian's mobile for the new login, if it is a valid and unused number."""
    if not raw:
        return None
    try:
        phone = normalize_phone(raw)
        await ensure_identity_available(db, phone=phone, phone_school_id=school_id)
    except (ValueError, IdentityInUse):
        return None
    return phone


async def _existing_parent(
    db: AsyncSession,
    school_id: int,
    guardian: Guardian,
    data: LoginCreate,
    email: str | None,
) -> User | None:
    """The parent login of this school this guardian should share, if there is one.

    Matched by the given email, then the given username, then the guardian's mobile number
    (unique per school). A match that is not a parent of this school is refused with the same
    generic answer as any taken email or username, so other schools are never revealed.
    """
    user: User | None = None
    taken: IdentityInUse | None = None
    if email is not None:
        user = await db.scalar(select(User).where(User.email == email))
        taken = IdentityInUse("Email already in use", "email_taken")
    if user is None and data.username is not None:
        user = await db.scalar(select(User).where(User.username == data.username))
        taken = IdentityInUse("Username already in use", "username_taken")
    if user is not None:
        if user.role != Role.PARENT or user.school_id != school_id:
            assert taken is not None
            raise taken
        return user
    try:
        phone = normalize_phone(guardian.phone)
    except ValueError:
        return None
    return await db.scalar(
        select(User).where(
            User.phone == phone, User.school_id == school_id, User.role == Role.PARENT
        )
    )


async def create_guardian_login(
    db: AsyncSession, actor: User, guardian_id: int, data: LoginCreate
) -> GuardianOut:
    guardian, student = await _get_guardian(db, actor, guardian_id)
    if guardian.user_id is not None:
        raise _conflict("Guardian already has a login")
    email = str(data.email).lower() if data.email is not None else None
    user = await _existing_parent(db, student.school_id, guardian, data, email)
    # Several students (siblings) can share one parent login: an existing one is linked to this
    # guardian too and its password is left untouched.
    if user is None:
        username = await _login_username(db, data)
        enforce_password(
            data.password,
            username=username,
            email=email,
            full_name=guardian.full_name,
            min_length=await settings_service.password_min_length(db, student.school_id),
        )
        user = User(
            school_id=student.school_id,
            branch_id=None,
            username=username,
            email=email,
            full_name=guardian.full_name,
            phone=await _parent_phone(db, guardian.phone, student.school_id),
            password_hash=hash_password(data.password),
            role=Role.PARENT,
            must_change_password=await settings_service.force_password_change(
                db, student.school_id
            ),
        )
        db.add(user)
        await db.flush()
    guardian.user_id = user.id
    await _commit_login(db)
    return _guardian_out(guardian)


async def remove_guardian_login(db: AsyncSession, actor: User, guardian_id: int) -> None:
    guardian, _ = await _get_guardian(db, actor, guardian_id)
    guardian.user_id = None
    await db.commit()


async def create_student_login(
    db: AsyncSession, actor: User, student_id: int, data: LoginCreate
) -> StudentDetail:
    student = await _get_student(db, actor, student_id)
    if not await settings_service.student_logins_enabled(db, student.school_id):
        raise ApiError(
            status.HTTP_403_FORBIDDEN, "Student logins are switched off for this school",
            "student_logins_disabled",
        )
    if student.user_id is not None:
        raise _conflict("Student already has a login")
    email = str(data.email).lower() if data.email is not None else None
    if email is not None:
        await ensure_identity_available(db, email=email)
    username = await _login_username(db, data)
    full_name = f"{student.first_name} {student.last_name}"
    enforce_password(
        data.password,
        username=username,
        email=email,
        full_name=full_name,
        min_length=await settings_service.password_min_length(db, student.school_id),
    )
    user = User(
        school_id=student.school_id,
        branch_id=student.branch_id,
        username=username,
        email=email,
        full_name=full_name,
        password_hash=hash_password(data.password),
        role=Role.STUDENT,
        must_change_password=await settings_service.force_password_change(
            db, student.school_id
        ),
    )
    db.add(user)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        raise IdentityInUse(
            "Username, email or mobile number already in use", IDENTITY_TAKEN_CODE
        ) from None
    student.user_id = user.id
    await _commit_login(db)
    return await _build_detail(db, student)


# ---- import ----


def _validation_message(exc: ValidationError) -> str:
    parts = []
    for err in exc.errors():
        loc = ".".join(str(p) for p in err["loc"])
        msg = err["msg"].removeprefix("Value error, ")
        parts.append(f"{loc}: {msg}" if loc else msg)
    return "; ".join(parts)


def _row_enrollment(
    row: ImportRow,
    year: AcademicYear | None,
    classes: dict[str, SchoolClass],
    sections: dict[tuple[int, str], Section],
) -> EnrollmentIn | None:
    if row.class_ is None:
        if row.section is not None or row.roll_no is not None:
            raise _unprocessable("class is required when section or roll_no is given")
        return None
    school_class = classes.get(row.class_.lower())
    if school_class is None:
        raise _unprocessable(f"Class '{row.class_}' not found in this branch")
    section_id = None
    if row.section is not None:
        section = sections.get((school_class.id, row.section.lower()))
        if section is None:
            raise _unprocessable(f"Section '{row.section}' not found in class '{row.class_}'")
        section_id = section.id
    if year is None:
        raise _unprocessable("No current academic year; pass academic_year_id")
    return EnrollmentIn(
        academic_year_id=year.id,
        class_id=school_class.id,
        section_id=section_id,
        roll_no=row.roll_no,
    )


async def import_students(db: AsyncSession, actor: User, data: ImportRequest) -> ImportResult:
    branch = await _resolve_branch(db, actor, data.branch_id)
    year_stmt = select(AcademicYear).where(AcademicYear.school_id == branch.school_id)
    if data.academic_year_id is not None:
        year = await db.scalar(year_stmt.where(AcademicYear.id == data.academic_year_id))
        if year is None:
            raise _not_found("Academic year")
    else:
        year = await db.scalar(year_stmt.where(AcademicYear.is_current))
    classes: dict[str, SchoolClass] = {}
    for c in await db.scalars(
        select(SchoolClass).where(SchoolClass.branch_id == branch.id).order_by(SchoolClass.level)
    ):
        classes.setdefault(c.name.strip().lower(), c)
    sections = {
        (s.class_id, s.name.strip().lower()): s
        for s in await db.scalars(select(Section).where(Section.branch_id == branch.id))
    }

    created = 0
    errors: list[ImportRowError] = []
    for number, raw in enumerate(data.rows, start=1):
        try:
            row = ImportRow.model_validate(raw)
            enrollment = _row_enrollment(row, year, classes, sections)
            fields = {
                "first_name": row.first_name,
                "last_name": row.last_name,
                "gender": row.gender,
                "date_of_birth": row.date_of_birth,
                "admission_date": row.admission_date,
                "admission_no": row.admission_no,
                "address": row.address,
                "previous_school": None,
            }
            guardian = GuardianCreate(
                full_name=row.guardian_name,
                relation=row.guardian_relation or GuardianRelation.GUARDIAN,
                phone=row.guardian_phone,
                is_primary=True,
            )
            # _insert_student works inside its own savepoint, so a failing row is rolled back
            # without affecting the rows already created.
            await _insert_student(db, branch, fields, [guardian], enrollment)
            created += 1
        except ValidationError as exc:
            errors.append(ImportRowError(row=number, message=_validation_message(exc)))
        except HTTPException as exc:
            errors.append(ImportRowError(row=number, message=str(exc.detail)))
    await audit.record(
        db, actor, "student.imported", "student", None,
        detail={"created": created, "failed": len(errors)},
        school_id=branch.school_id, branch_id=branch.id,
    )
    await db.commit()
    return ImportResult(created=created, failed=len(errors), errors=errors)
