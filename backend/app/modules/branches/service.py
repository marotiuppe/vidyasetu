from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.tenant import scope_branches
from app.modules.branches.models import Branch
from app.modules.branches.schemas import BranchCreate, BranchUpdate
from app.modules.schools.models import School
from app.modules.users.models import Role, User


async def list_branches(db: AsyncSession, actor: User) -> list[Branch]:
    result = await db.scalars(scope_branches(select(Branch), actor).order_by(Branch.id))
    return list(result)


async def get_branch(db: AsyncSession, actor: User, branch_id: int) -> Branch:
    branch = await db.scalar(scope_branches(select(Branch), actor).where(Branch.id == branch_id))
    if branch is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Branch not found")
    return branch


async def create_branch(db: AsyncSession, actor: User, data: BranchCreate) -> Branch:
    school_id = data.school_id if actor.role == Role.SUPER_ADMIN else actor.school_id
    if school_id is None or await db.get(School, school_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="School not found")
    branch = Branch(school_id=school_id, name=data.name, code=data.code)
    db.add(branch)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Branch code already used") from None
    return branch


async def update_branch(
    db: AsyncSession, actor: User, branch_id: int, data: BranchUpdate
) -> Branch:
    branch = await get_branch(db, actor, branch_id)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(branch, field, value)
    await db.commit()
    return branch
