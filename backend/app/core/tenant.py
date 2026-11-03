"""Central tenant isolation. All tenant-owned queries must be filtered through here."""

from datetime import date
from typing import Any

from sqlalchemy import Select, and_, exists, false, or_, select

from app.modules.academics.models import AcademicYear
from app.modules.admissions.models import AdmissionApplication
from app.modules.attendance.models import Holiday
from app.modules.branches.models import Branch
from app.modules.exams.models import GradeScale
from app.modules.notices.models import Notice, TargetType
from app.modules.promotion.models import PromotionBatch, PromotionItem
from app.modules.students.models import Enrollment, Guardian, Student, StudentStatus
from app.modules.users.models import Role, User

# Staff who may read exam data of their school or branch (teachers enter marks; clerks read).
EXAM_STAFF = frozenset(
    {Role.SCHOOL_OWNER, Role.MANAGEMENT, Role.HEADMASTER, Role.TEACHER, Role.CLERK}
)

type AnySelect = Select[*tuple[Any, ...]]


def scope_branches(stmt: AnySelect, user: User) -> AnySelect:
    """Restrict a branch query to what `user` is allowed to see."""
    if user.role == Role.SUPER_ADMIN:
        return stmt
    if user.school_id is None:
        return stmt.where(false())
    stmt = stmt.where(Branch.school_id == user.school_id)
    if user.branch_id is not None:
        stmt = stmt.where(Branch.id == user.branch_id)
    return stmt


def scope_tenant(stmt: AnySelect, model: Any, user: User) -> AnySelect:
    """Generic scope for any model with `school_id` (and optionally `branch_id`)."""
    if user.role == Role.SUPER_ADMIN:
        return stmt
    if user.school_id is None:
        return stmt.where(false())
    stmt = stmt.where(model.school_id == user.school_id)
    if user.branch_id is not None and hasattr(model, "branch_id"):
        stmt = stmt.where(model.branch_id == user.branch_id)
    return stmt


def scope_fees(stmt: AnySelect, model: Any, user: User) -> AnySelect:
    """Scope for fee data (heads, structure, invoices, payments) read or changed by fee staff.

    Fee staff see their branch (school owner: the whole school). Super admins, parents, students
    and teachers get nothing here: parents and students reach fees only through `scope_students`.
    """
    if user.role in (Role.SUPER_ADMIN, Role.PARENT, Role.STUDENT, Role.TEACHER):
        return stmt.where(false())
    return scope_tenant(stmt, model, user)


def scope_admissions(stmt: AnySelect, user: User) -> AnySelect:
    """Admission applications: the school owner sees the whole school, other staff only their
    branch. A branch-level user without a branch sees nothing (never the whole school)."""
    if user.role == Role.SUPER_ADMIN or user.school_id is None:
        return stmt.where(false())
    stmt = stmt.where(AdmissionApplication.school_id == user.school_id)
    if user.role == Role.SCHOOL_OWNER:
        return stmt
    if user.branch_id is None:
        return stmt.where(false())
    return stmt.where(AdmissionApplication.branch_id == user.branch_id)


def scope_exams(stmt: AnySelect, model: Any, user: User) -> AnySelect:
    """Exam data (terms, subjects, exams, marks, aspects, remarks) of a model with school_id and
    branch_id. Only exam staff; the school owner sees the whole school, others their branch.
    Parents, students and accountants get nothing here (families reach results through
    `scope_students`)."""
    if user.role not in EXAM_STAFF or user.school_id is None:
        return stmt.where(false())
    stmt = stmt.where(model.school_id == user.school_id)
    if user.role == Role.SCHOOL_OWNER:
        return stmt
    if user.branch_id is None:
        return stmt.where(false())
    return stmt.where(model.branch_id == user.branch_id)


def scope_grading(stmt: AnySelect, user: User) -> AnySelect:
    """Grading scales are school-wide: any exam staff of the school may read them."""
    if user.role not in EXAM_STAFF or user.school_id is None:
        return stmt.where(false())
    return stmt.where(GradeScale.school_id == user.school_id)


def scope_users(stmt: AnySelect, user: User) -> AnySelect:
    if user.role == Role.SUPER_ADMIN:
        return stmt
    if user.school_id is None:
        return stmt.where(false())
    stmt = stmt.where(User.school_id == user.school_id)
    if user.branch_id is not None:
        stmt = stmt.where(User.branch_id == user.branch_id)
    return stmt


def scope_students(stmt: AnySelect, user: User) -> AnySelect:
    """Restrict a student query (any select that includes `Student`) to what `user` may see.

    Staff see their branch (school owner: whole school, super admin: everything); a parent only
    sees students with a guardian linked to them; a student only sees themself.
    """
    if user.role == Role.SUPER_ADMIN:
        return stmt
    if user.school_id is None:
        return stmt.where(false())
    stmt = stmt.where(Student.school_id == user.school_id)
    if user.role == Role.PARENT:
        return stmt.where(
            Student.id.in_(select(Guardian.student_id).where(Guardian.user_id == user.id))
        )
    if user.role == Role.STUDENT:
        return stmt.where(Student.user_id == user.id)
    if user.role == Role.SCHOOL_OWNER:
        return stmt
    if user.branch_id is None:
        return stmt.where(false())
    return stmt.where(Student.branch_id == user.branch_id)


def scope_promotion_batches(stmt: AnySelect, user: User) -> AnySelect:
    """Year-end promotion batches: the school owner sees all of the school's; branch-level staff
    see only batches that moved a student from or to their branch. Others see nothing."""
    if user.role == Role.SUPER_ADMIN or user.school_id is None:
        return stmt.where(false())
    stmt = stmt.where(PromotionBatch.school_id == user.school_id)
    if user.role == Role.SCHOOL_OWNER:
        return stmt
    if user.branch_id is None:
        return stmt.where(false())
    touched = exists().where(
        PromotionItem.batch_id == PromotionBatch.id,
        or_(
            PromotionItem.from_branch_id == user.branch_id,
            PromotionItem.to_branch_id == user.branch_id,
        ),
    )
    return stmt.where(touched)


def scope_holidays(stmt: AnySelect, user: User) -> AnySelect:
    """Holidays visible to `user`: school-wide ones plus their branch's (owner: all of the school).

    Users without a branch (e.g. parents) only see school-wide holidays.
    """
    if user.role == Role.SUPER_ADMIN:
        return stmt
    if user.school_id is None:
        return stmt.where(false())
    stmt = stmt.where(Holiday.school_id == user.school_id)
    if user.role == Role.SCHOOL_OWNER:
        return stmt
    if user.branch_id is None:
        return stmt.where(Holiday.branch_id.is_(None))
    return stmt.where(or_(Holiday.branch_id.is_(None), Holiday.branch_id == user.branch_id))


def notice_manager_clause(user: User) -> Any:
    """SQL condition: `user` administers the notice (owner, or branch management/headmaster)."""
    if user.role == Role.SCHOOL_OWNER:
        return Notice.school_id == user.school_id
    if user.role in (Role.MANAGEMENT, Role.HEADMASTER) and user.branch_id is not None:
        return Notice.branch_id == user.branch_id
    return Notice.id.is_(None)  # never true


def scope_notices(
    stmt: AnySelect, user: User, today: date, *, only_active: bool = False
) -> AnySelect:
    """Restrict a notice query to what `user` may see.

    Expired notices are hidden unless the user wrote them or administers them
    (`only_active=True` hides them for everyone, e.g. for unread counts).
    """
    if user.role == Role.SUPER_ADMIN or user.school_id is None:
        return stmt.where(false())
    stmt = stmt.where(Notice.school_id == user.school_id)
    live = or_(Notice.expires_on.is_(None), Notice.expires_on >= today)
    if only_active:
        stmt = stmt.where(live)
    if user.role == Role.SCHOOL_OWNER:
        return stmt
    school_wide = Notice.target_type == TargetType.SCHOOL
    if user.role in (Role.PARENT, Role.STUDENT):
        active = Student.status == StudentStatus.ACTIVE
        children = scope_students(select(Student.id), user).where(active)
        child_branches = scope_students(select(Student.branch_id), user).where(active)
        placements = (
            select(Enrollment.class_id, Enrollment.section_id)
            .join(AcademicYear, AcademicYear.id == Enrollment.academic_year_id)
            .where(
                AcademicYear.school_id == user.school_id,
                AcademicYear.is_current.is_(True),
                Enrollment.student_id.in_(children),
            )
            .subquery()
        )
        visible = or_(
            school_wide,
            and_(Notice.target_type == TargetType.BRANCH, Notice.branch_id.in_(child_branches)),
            and_(
                Notice.target_type == TargetType.CLASS,
                Notice.class_id.in_(select(placements.c.class_id)),
            ),
            and_(
                Notice.target_type == TargetType.SECTION,
                Notice.section_id.in_(
                    select(placements.c.section_id).where(placements.c.section_id.is_not(None))
                ),
            ),
        )
        return stmt.where(visible, live)  # parents and students never see expired notices
    if user.branch_id is None:
        visible = school_wide
    else:
        visible = or_(school_wide, Notice.branch_id == user.branch_id)
    stmt = stmt.where(visible)
    if not only_active:
        stmt = stmt.where(or_(live, Notice.created_by == user.id, notice_manager_clause(user)))
    return stmt
