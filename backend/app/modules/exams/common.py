"""Shared helpers for the exam services: role sets, branch and record lookups, the section roster
and error builders. Every lookup goes through the tenant scope helpers."""

from fastapi import status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ApiError
from app.core.tenant import scope_branches, scope_exams
from app.modules.academics.models import AcademicYear, SchoolClass, Section
from app.modules.branches.models import Branch
from app.modules.exams.models import Exam, ExamTerm, Subject
from app.modules.students.models import Enrollment, Student, StudentStatus
from app.modules.users.models import Role, User

# Who may configure exams, enter marks and see the school's report data.
CONFIG_ROLES = frozenset({Role.SCHOOL_OWNER, Role.MANAGEMENT, Role.HEADMASTER})
# Teachers of the branch enter marks and aspect grades (no teacher-section assignment exists yet).
MARK_ROLES = CONFIG_ROLES | {Role.TEACHER}
# Families see results only through the student scope; accountants never see exam data.
RESULT_STAFF_ROLES = CONFIG_ROLES | {Role.TEACHER, Role.CLERK}
FAMILY_ROLES = frozenset({Role.PARENT, Role.STUDENT})


def not_found(what: str) -> ApiError:
    return ApiError(status.HTTP_404_NOT_FOUND, f"{what} not found", "not_found")


def unprocessable(detail: str, code: str = "unprocessable") -> ApiError:
    return ApiError(422, detail, code)


def conflict(detail: str, code: str) -> ApiError:
    return ApiError(status.HTTP_409_CONFLICT, detail, code)


def forbidden() -> ApiError:
    return ApiError(status.HTTP_403_FORBIDDEN, "Not allowed", "forbidden")


def require_role(actor: User, allowed: frozenset[Role]) -> None:
    if actor.role not in allowed:
        raise forbidden()


async def resolve_branch(db: AsyncSession, actor: User, branch_id: int | None) -> Branch:
    """The branch a write applies to. Branch-level users always use their own branch; the school
    owner names one of the school's branches."""
    if actor.branch_id is not None:
        if branch_id is not None and branch_id != actor.branch_id:
            raise not_found("Branch")
        wanted = actor.branch_id
    else:
        if branch_id is None:
            raise unprocessable("branch_id is required", "branch_required")
        wanted = branch_id
    branch: Branch | None = await db.scalar(
        scope_branches(select(Branch), actor).where(Branch.id == wanted)
    )
    if branch is None:
        raise not_found("Branch")
    return branch


async def branch_filter(db: AsyncSession, actor: User, branch_id: int | None) -> int | None:
    """Optional branch filter for reads: None means every branch the user may see."""
    if actor.branch_id is not None:
        if branch_id is not None and branch_id != actor.branch_id:
            raise not_found("Branch")
        return actor.branch_id
    if branch_id is None:
        return None
    branch: Branch | None = await db.scalar(
        scope_branches(select(Branch), actor).where(Branch.id == branch_id)
    )
    if branch is None:
        raise not_found("Branch")
    return branch.id


async def get_term(db: AsyncSession, actor: User, term_id: int) -> ExamTerm:
    term: ExamTerm | None = await db.scalar(
        scope_exams(select(ExamTerm), ExamTerm, actor).where(ExamTerm.id == term_id)
    )
    if term is None:
        raise not_found("Term")
    return term


async def get_exam(db: AsyncSession, actor: User, exam_id: int) -> tuple[Exam, ExamTerm]:
    row = (
        await db.execute(
            scope_exams(select(Exam, ExamTerm), Exam, actor)
            .join(ExamTerm, ExamTerm.id == Exam.term_id)
            .where(Exam.id == exam_id)
        )
    ).first()
    if row is None:
        raise not_found("Exam")
    return row[0], row[1]


async def get_section(
    db: AsyncSession, actor: User, section_id: int, branch_id: int
) -> tuple[Section, SchoolClass]:
    row = (
        await db.execute(
            scope_exams(select(Section, SchoolClass), Section, actor)
            .join(SchoolClass, SchoolClass.id == Section.class_id)
            .where(Section.id == section_id, Section.branch_id == branch_id)
        )
    ).first()
    if row is None:
        raise not_found("Section")
    return row[0], row[1]


async def get_subject(db: AsyncSession, actor: User, subject_id: int, branch_id: int) -> Subject:
    subject: Subject | None = await db.scalar(
        scope_exams(select(Subject), Subject, actor).where(
            Subject.id == subject_id, Subject.branch_id == branch_id
        )
    )
    if subject is None:
        raise not_found("Subject")
    return subject


async def year_of(db: AsyncSession, term: ExamTerm) -> AcademicYear:
    year: AcademicYear | None = await db.scalar(
        select(AcademicYear).where(
            AcademicYear.id == term.academic_year_id, AcademicYear.school_id == term.school_id
        )
    )
    if year is None:
        raise not_found("Academic year")
    return year


async def section_roster(
    db: AsyncSession, section: Section, year_id: int
) -> list[tuple[Student, Enrollment]]:
    """Active students placed in `section` for the year, by roll number (unnumbered last)."""
    rows = await db.execute(
        select(Student, Enrollment)
        .join(Enrollment, Enrollment.student_id == Student.id)
        .where(
            Enrollment.section_id == section.id,
            Enrollment.academic_year_id == year_id,
            Enrollment.branch_id == section.branch_id,
            Student.status == StudentStatus.ACTIVE,
        )
        .order_by(Enrollment.roll_no.is_(None), Enrollment.roll_no, Student.id)
    )
    return [(s, e) for s, e in rows.all()]


def student_name(student: Student) -> str:
    return f"{student.first_name} {student.last_name}".strip()
