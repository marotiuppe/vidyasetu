from typing import Annotated, Any, Literal

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field, model_validator

from app.core.config import get_settings
from app.core.deps import CurrentUser, DbSession, require_cookie_request
from app.core.password_policy import enforce_password
from app.core.security import create_token, decode_mfa_token, hash_password, verify_password
from app.modules.audit import service as audit
from app.modules.auth import service
from app.modules.settings import service as settings_service
from app.modules.users.models import User
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


class MeOut(UserOut):
    # Policy requires two-factor for this role and the user has not set it up yet.
    mfa_setup_required: bool


class TokenResponse(BaseModel):
    mfa_required: Literal[False] = False
    access_token: str
    token_type: str = "bearer"
    user: MeOut


class MfaChallenge(BaseModel):
    """Returned instead of a session when the account has two-factor on."""

    mfa_required: Literal[True] = True
    mfa_token: str


class MfaLoginRequest(BaseModel):
    mfa_token: str = Field(min_length=1, max_length=2000)
    code: str | None = Field(default=None, min_length=1, max_length=20)
    recovery_code: str | None = Field(default=None, min_length=1, max_length=40)
    remember_me: bool | None = None

    @model_validator(mode="after")
    def _one_code(self) -> "MfaLoginRequest":
        if (self.code is None) == (self.recovery_code is None):
            raise ValueError("Send either code or recovery_code")
        return self


async def me_out(db: DbSession, user: User) -> MeOut:
    required = not user.mfa_enabled and await settings_service.mfa_required(db, user)
    return MeOut(**UserOut.model_validate(user).model_dump(), mfa_setup_required=required)


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


async def _token_response(
    response: Response, session: service.Session, db: DbSession
) -> TokenResponse:
    _set_refresh_cookie(response, session.refresh_token, session.remember_me)
    return TokenResponse(
        access_token=session.access_token, user=await me_out(db, session.user)
    )


@router.get("/options", response_model=AuthOptions)
async def auth_options() -> AuthOptions:
    return AuthOptions(password_reset_enabled=_password_reset_enabled())


@router.post(
    "/login",
    response_model=TokenResponse | MfaChallenge,
    dependencies=[Depends(require_cookie_request)],
)
async def login(
    data: LoginRequest, response: Response, db: DbSession
) -> TokenResponse | MfaChallenge:
    user = await service.authenticate(db, data.identifier, data.password)
    if user is None:
        raise _invalid
    if user.mfa_enabled:
        # No session and no cookie until the second step succeeds.
        return MfaChallenge(
            mfa_token=create_token(
                user.id, "mfa", {"tv": user.token_version, "rem": data.remember_me}
            )
        )
    await audit.record(db, user, "auth.login_ok", "user", user.id, detail={"mfa": False})
    session = await service.start_session(db, user, data.remember_me)
    return await _token_response(response, session, db)


@router.post(
    "/login/mfa",
    response_model=TokenResponse,
    dependencies=[Depends(require_cookie_request)],
)
async def login_mfa(data: MfaLoginRequest, response: Response, db: DbSession) -> TokenResponse:
    claims = decode_mfa_token(data.mfa_token)
    if claims is None:
        raise _invalid
    remember = claims.remember_me if data.remember_me is None else data.remember_me
    session = await service.complete_mfa_login(
        db, claims.user_id, claims.token_version, data.code, data.recovery_code, remember
    )
    if session is None:
        raise _invalid
    return await _token_response(response, session, db)


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
    return await _token_response(response, session, db)


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


@router.get("/me", response_model=MeOut)
async def me(db: DbSession, user: CurrentUser) -> MeOut:
    return await me_out(db, user)


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
        min_length=await settings_service.password_min_length(db, user.school_id),
    )
    user.password_hash = hash_password(data.new_password)
    user.must_change_password = False
    await service.revoke_user_sessions(db, user)
    await audit.record(db, user, "auth.password_changed", "user", user.id)
    await db.commit()
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    _delete_refresh_cookie(response)
    return response
