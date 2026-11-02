from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_token
from app.db.session import get_db
from app.modules.schools.models import School
from app.modules.users.models import Role, User

bearer = HTTPBearer(auto_error=False)
DbSession = Annotated[AsyncSession, Depends(get_db)]

_UNAUTHORIZED = HTTPException(
    status.HTTP_401_UNAUTHORIZED,
    detail="Not authenticated",
    headers={"WWW-Authenticate": "Bearer"},
)


async def get_current_user(
    db: DbSession,
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> User:
    if creds is None:
        raise _UNAUTHORIZED
    user_id = decode_token(creds.credentials, "access")
    if user_id is None:
        raise _UNAUTHORIZED
    user = await db.get(User, user_id)
    if user is None or not user.is_active:
        raise _UNAUTHORIZED
    if user.school_id is not None:
        school = await db.get(School, user.school_id)
        if school is None or not school.is_active:
            raise _UNAUTHORIZED
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_roles(*roles: Role) -> Callable[[User], User]:
    allowed = set(roles)

    def checker(user: CurrentUser) -> User:
        if user.role not in allowed:
            raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Not allowed")
        return user

    return checker
