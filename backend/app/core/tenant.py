"""Central tenant isolation. All tenant-owned queries must be filtered through here."""

from typing import Any

from sqlalchemy import Select, or_, select

from app.modules.attendance.models import Holiday
from app.modules.branches.models import Branch
from app.modules.students.models import Guardian, Student
from app.modules.users.models import Role, User


def scope_branches(stmt: Select[tuple[Branch]], user: User) -> Select[tuple[Branch]]:
    """Restrict a branch query to what `user` is allowed to see."""
    if user.role == Role.SUPER_ADMIN:
        return stmt
    if user.school_id is None:
        return stmt.where(False)
    stmt = stmt.where(Branch.school_id == user.school_id)
    if user.branch_id is not None:
        stmt = stmt.where(Branch.id == user.branch_id)
    return stmt


def scope_tenant(stmt: Select[Any], model: Any, user: User) -> Select[Any]:
    """Generic scope for any model with `school_id` (and optionally `branch_id`)."""
    if user.role == Role.SUPER_ADMIN:
        return stmt
    if user.school_id is None:
        return stmt.where(False)
    stmt = stmt.where(model.school_id == user.school_id)
    if user.branch_id is not None and hasattr(model, "branch_id"):
        stmt = stmt.where(model.branch_id == user.branch_id)
    return stmt


def scope_users(stmt: Select[tuple[User]], user: User) -> Select[tuple[User]]:
    if user.role == Role.SUPER_ADMIN:
        return stmt
    if user.school_id is None:
        return stmt.where(False)
    stmt = stmt.where(User.school_id == user.school_id)
    if user.branch_id is not None:
        stmt = stmt.where(User.branch_id == user.branch_id)
    return stmt


def scope_students(stmt: Select[Any], user: User) -> Select[Any]:
    """Restrict a student query (any select that includes `Student`) to what `user` may see.

    Staff see their branch (school owner: whole school, super admin: everything); a parent only
    sees students with a guardian linked to them; a student only sees themself.
    """
    if user.role == Role.SUPER_ADMIN:
        return stmt
    if user.school_id is None:
        return stmt.where(False)
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
        return stmt.where(False)
    return stmt.where(Student.branch_id == user.branch_id)


def scope_holidays(stmt: Select[tuple[Holiday]], user: User) -> Select[tuple[Holiday]]:
    """Holidays visible to `user`: school-wide ones plus their branch's (owner: all of the school).

    Users without a branch (e.g. parents) only see school-wide holidays.
    """
    if user.role == Role.SUPER_ADMIN:
        return stmt
    if user.school_id is None:
        return stmt.where(False)
    stmt = stmt.where(Holiday.school_id == user.school_id)
    if user.role == Role.SCHOOL_OWNER:
        return stmt
    if user.branch_id is None:
        return stmt.where(Holiday.branch_id.is_(None))
    return stmt.where(or_(Holiday.branch_id.is_(None), Holiday.branch_id == user.branch_id))
