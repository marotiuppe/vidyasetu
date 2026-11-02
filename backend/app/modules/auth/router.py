from typing import Annotated, Any

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field, model_validator

from app.core.config import get_settings
from app.core.deps import CurrentUser, DbSession, require_cookie_request
from app.core.password_policy import enforce_password
from app.core.security import hash_password, verify_password
from app.modules.auth import service
from app.modules.users.schemas import UserOut

router = APIRouter(prefix="/auth", tags=["auth"])

REFRESH_COOKIE = "refresh_token"
REFRESH_COOKIE_PATH = "/api/v1/auth"
_invalid = HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
_session_expired = HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Session expired")


class LoginRequest(BaseModel):
    # Email, mobile number or username. The legacy `email` field is accepted as an alias.
    identifier: str = Field(min_length=1, max_length=254)
    password: str = Field(min_length=1, max_length=128)
    remember_me: bool = False

    @model_validator(mode="before")
    @classmethod
    def _email_alias(cls, data: Any) -> Any:
        if isinstance(data, dict) and data.get("identifier") is None:
            if data.get("email") is not None:
                return {**data, "identifier": data["email"]}
        return data


class AuthOptions(BaseModel):
    password_reset_enabled: bool


def _password_reset_enabled() -> bool:
    # Becomes true in phase 11, once an email or SMS adapter is configured.
    return False


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(max_length=128)
    new_password: str = Field(max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


def _set_refresh_cookie(response: Response, token: str, remember_me: bool) -> None:
    settings = get_settings()
    # Remembered sessions persist for refresh_token_days; otherwise the cookie is a session
    # cookie that the browser drops when it closes.
    response.set_cookie(
        REFRESH_COOKIE,
        token,
        max_age=settings.refresh_token_days * 86400 if remember_me else None,
        httponly=True,
        secure=settings.is_production,
        samesite="strict",
        path=REFRESH_COOKIE_PATH,
    )


def _delete_refresh_cookie(response: Response) -> None:
    response.delete_cookie(
        REFRESH_COOKIE,
        path=REFRESH_COOKIE_PATH,
        httponly=True,
        secure=get_settings().is_production,
        samesite="strict",
    )


def _token_response(response: Response, session: service.Session) -> TokenResponse:
    _set_refresh_cookie(response, session.refresh_token, session.remember_me)
    return TokenResponse(
        access_token=session.access_token, user=UserOut.model_validate(session.user)
    )


@router.get("/options", response_model=AuthOptions)
async def auth_options() -> AuthOptions:
    return AuthOptions(password_reset_enabled=_password_reset_enabled())


@router.post(
    "/login",
    response_model=TokenResponse,
    dependencies=[Depends(require_cookie_request)],
)
async def login(data: LoginRequest, response: Response, db: DbSession) -> TokenResponse:
    user = await service.authenticate(db, data.identifier, data.password)
    if user is None:
        raise _invalid
    session = await service.start_session(db, user, data.remember_me)
    return _token_response(response, session)


@router.post(
    "/refresh",
    response_model=TokenResponse,
    dependencies=[Depends(require_cookie_request)],
)
async def refresh(
    response: Response,
    db: DbSession,
    refresh_token: Annotated[str | None, Cookie()] = None,
) -> TokenResponse:
    session = await service.rotate_session(db, refresh_token) if refresh_token else None
    if session is None:
        raise _session_expired
    return _token_response(response, session)


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_cookie_request)],
)
async def logout(
    response: Response,
    db: DbSession,
    refresh_token: Annotated[str | None, Cookie()] = None,
) -> None:
    if refresh_token:
        await service.end_session(db, refresh_token)
    _delete_refresh_cookie(response)


@router.get("/me", response_model=UserOut)
async def me(user: CurrentUser) -> UserOut:
    return UserOut.model_validate(user)


@router.post("/change-password", status_code=status.HTTP_204_NO_CONTENT)
async def change_password(
    data: ChangePasswordRequest, db: DbSession, user: CurrentUser
) -> Response:
    """Change the own password. This ends every session, so the user signs in again."""
    if not verify_password(data.current_password, user.password_hash):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Current password is incorrect")
    if verify_password(data.new_password, user.password_hash):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail="New password must be different from the current password",
        )
    enforce_password(
        data.new_password,
        username=user.username,
        email=user.email,
        full_name=user.full_name,
    )
    user.password_hash = hash_password(data.new_password)
    user.must_change_password = False
    await service.revoke_user_sessions(db, user)
    await db.commit()
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    _delete_refresh_cookie(response)
    return response
