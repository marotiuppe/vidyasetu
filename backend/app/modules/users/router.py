from fastapi import APIRouter, Depends, Query, Response, status

from app.core.deps import CurrentUser, DbSession, require_roles
from app.modules.users import service
from app.modules.users.models import Role
from app.modules.users.schemas import PasswordReset, UserCreate, UserOut, UserUpdate

router = APIRouter(prefix="/users", tags=["users"])

_managers = require_roles(
    Role.SUPER_ADMIN, Role.SCHOOL_OWNER, Role.MANAGEMENT, Role.HEADMASTER
)


@router.get("", response_model=list[UserOut], dependencies=[Depends(_managers)])
async def list_users(
    db: DbSession,
    actor: CurrentUser,
    role: Role | None = None,
    branch_id: int | None = None,
    is_active: bool | None = None,
    q: str | None = Query(default=None, max_length=100),
) -> list[UserOut]:
    users = await service.list_users(
        db, actor, role=role, branch_id=branch_id, is_active=is_active, q=q
    )
    return [UserOut.model_validate(u) for u in users]


@router.post(
    "",
    response_model=UserOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(_managers)],
)
async def create_user(data: UserCreate, db: DbSession, actor: CurrentUser) -> UserOut:
    return UserOut.model_validate(await service.create_user(db, actor, data))


@router.get("/{user_id}", response_model=UserOut, dependencies=[Depends(_managers)])
async def get_user(user_id: int, db: DbSession, actor: CurrentUser) -> UserOut:
    return UserOut.model_validate(await service.get_user(db, actor, user_id))


@router.patch("/{user_id}", response_model=UserOut, dependencies=[Depends(_managers)])
async def update_user(
    user_id: int, data: UserUpdate, db: DbSession, actor: CurrentUser
) -> UserOut:
    return UserOut.model_validate(await service.update_user(db, actor, user_id, data))


@router.post(
    "/{user_id}/reset-password",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(_managers)],
)
async def reset_password(
    user_id: int, data: PasswordReset, db: DbSession, actor: CurrentUser
) -> Response:
    await service.reset_password(db, actor, user_id, data.new_password)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/{user_id}/unlock",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(_managers)],
)
async def unlock_user(user_id: int, db: DbSession, actor: CurrentUser) -> Response:
    await service.unlock_user(db, actor, user_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/{user_id}/mfa/reset",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_roles(Role.SUPER_ADMIN, Role.SCHOOL_OWNER))],
)
async def reset_mfa(user_id: int, db: DbSession, actor: CurrentUser) -> Response:
    await service.reset_mfa(db, actor, user_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
