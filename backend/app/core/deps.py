from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import ApiError
from app.core.security import decode_access_token
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

# Endpoints a user may still call while a forced password change is pending.
PASSWORD_CHANGE_EXEMPT = frozenset(
    {
        "/api/v1/auth/me",
        "/api/v1/auth/change-password",
        "/api/v1/auth/logout",
        "/api/v1/auth/refresh",
    }
)


async def get_current_user(
    request: Request,
    db: DbSession,
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> User:
    if creds is None:
        raise _UNAUTHORIZED
    claims = decode_access_token(creds.credentials)
    if claims is None:
        raise _UNAUTHORIZED
    user = await db.get(User, claims.user_id)
    if user is None or not user.is_active:
        raise _UNAUTHORIZED
    if claims.token_version != user.token_version:
        # Password changed, reset, or the account was deactivated since this token was issued.
        raise _UNAUTHORIZED
    if user.school_id is not None:
        school = await db.get(School, user.school_id)
        if school is None or not school.is_active:
            raise _UNAUTHORIZED
    if user.must_change_password and request.url.path not in PASSWORD_CHANGE_EXEMPT:
        raise ApiError(
            status.HTTP_403_FORBIDDEN,
            "Password change required",
            "password_change_required",
        )
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_roles(*roles: Role) -> Callable[[User], User]:
    allowed = set(roles)

    def checker(user: CurrentUser) -> User:
        if user.role not in allowed:
            raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Not allowed")
        return user

    return checker


def require_cookie_request(request: Request) -> None:
    """CSRF and origin checks for the cookie-based auth endpoints (login, refresh, logout).

    The browser cannot send a custom header in a cross-site form post, so requiring one blocks
    CSRF. A present Origin must be an allowed origin or this server's own origin.
    """
    if request.headers.get("x-requested-with") != "XMLHttpRequest":
        raise ApiError(status.HTTP_403_FORBIDDEN, "Request rejected", "csrf_rejected")
    origin = request.headers.get("origin")
    if origin is not None:
        own = f"{request.url.scheme}://{request.url.netloc}"
        if origin != own and origin not in get_settings().allowed_origins:
            raise ApiError(status.HTTP_403_FORBIDDEN, "Request rejected", "csrf_rejected")
