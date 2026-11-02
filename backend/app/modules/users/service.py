from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.core.tenant import scope_users
from app.modules.branches.models import Branch
from app.modules.users.models import BRANCH_ROLES, Role, User
from app.modules.users.schemas import UserCreate

# Which roles each role may create.
CREATABLE: dict[Role, set[Role]] = {
    Role.SUPER_ADMIN: set(Role),
    Role.SCHOOL_OWNER: set(Role) - {Role.SUPER_ADMIN},
    Role.MANAGEMENT: {Role.TEACHER, Role.ACCOUNTANT, Role.CLERK, Role.STUDENT, Role.PARENT},
    Role.HEADMASTER: {Role.TEACHER, Role.ACCOUNTANT, Role.CLERK, Role.STUDENT, Role.PARENT},
}


async def list_users(db: AsyncSession, actor: User) -> list[User]:
    result = await db.scalars(scope_users(select(User), actor).order_by(User.id))
    return list(result)


async def get_user(db: AsyncSession, actor: User, user_id: int) -> User:
    user = await db.scalar(scope_users(select(User), actor).where(User.id == user_id))
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


async def create_user(db: AsyncSession, actor: User, data: UserCreate) -> User:
    if data.role not in CREATABLE.get(actor.role, set()):
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Not allowed to create this role")

    school_id: int | None
    branch_id: int | None = None

    if data.role == Role.SUPER_ADMIN:
        school_id = None
    else:
        school_id = data.school_id if actor.role == Role.SUPER_ADMIN else actor.school_id
        if school_id is None:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail="school_id required")
        if data.role in BRANCH_ROLES:
            # Branch-level creators can only create inside their own branch.
            branch_id = actor.branch_id if actor.branch_id is not None else data.branch_id
            if branch_id is None:
                raise HTTPException(
                    status.HTTP_422_UNPROCESSABLE_ENTITY, detail="branch_id required"
                )
            branch = await db.scalar(
                select(Branch).where(Branch.id == branch_id, Branch.school_id == school_id)
            )
            if branch is None:
                raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Branch not found")

    user = User(
        school_id=school_id,
        branch_id=branch_id,
        email=data.email.lower(),
        full_name=data.full_name,
        phone=data.phone,
        password_hash=hash_password(data.password),
        role=data.role,
    )
    db.add(user)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Email already in use") from None
    return user
