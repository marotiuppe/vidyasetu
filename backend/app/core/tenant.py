"""Central tenant isolation. All tenant-owned queries must be filtered through here."""

from typing import Any

from sqlalchemy import Select

from app.modules.branches.models import Branch
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
