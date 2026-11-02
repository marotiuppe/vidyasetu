from fastapi import APIRouter, Depends, status

from app.core.deps import CurrentUser, DbSession, require_roles
from app.modules.users import service
from app.modules.users.models import Role
from app.modules.users.schemas import UserCreate, UserOut

router = APIRouter(prefix="/users", tags=["users"])

_managers = require_roles(
    Role.SUPER_ADMIN, Role.SCHOOL_OWNER, Role.MANAGEMENT, Role.HEADMASTER
)


@router.get("", response_model=list[UserOut], dependencies=[Depends(_managers)])
async def list_users(db: DbSession, actor: CurrentUser) -> list[UserOut]:
    return [UserOut.model_validate(u) for u in await service.list_users(db, actor)]


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
