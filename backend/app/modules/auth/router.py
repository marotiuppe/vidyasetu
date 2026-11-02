from typing import Annotated, Any

from fastapi import APIRouter, Cookie, HTTPException, Response, status
from pydantic import BaseModel, Field, StringConstraints, model_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.deps import CurrentUser, DbSession
from app.core.security import (
    DUMMY_HASH,
    create_token,
    decode_refresh_token,
    hash_password,
    verify_password,
)
from app.modules.schools.models import School
from app.modules.users.identity import detect_kind, normalize_email, normalize_phone
from app.modules.users.models import User
from app.modules.users.schemas import UserOut

router = APIRouter(prefix="/auth", tags=["auth"])

REFRESH_COOKIE = "refresh_token"
_invalid = HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")


class LoginRequest(BaseModel):
    # Email, mobile number or username. The legacy `email` field is accepted as an alias.
    identifier: Annotated[str, StringConstraints(min_length=1, max_length=254)]
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
    new_password: str = Field(min_length=8, max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


def _set_refresh_cookie(response: Response, user_id: int, remember_me: bool) -> None:
    settings = get_settings()
    # Remembered sessions persist for refresh_token_days; otherwise the cookie is a session
    # cookie that the browser drops when it closes.
    response.set_cookie(
        REFRESH_COOKIE,
        create_token(user_id, "refresh", {"rem": remember_me}),
        max_age=settings.refresh_token_days * 86400 if remember_me else None,
        httponly=True,
        secure=settings.is_production,
        samesite="lax",
        path="/api/v1/auth",
    )


async def _school_active(db: DbSession, user: User) -> bool:
    if user.school_id is None:
        return True
    school = await db.get(School, user.school_id)
    return school is not None and school.is_active


async def _find_login_users(db: AsyncSession, identifier: str) -> list[User]:
    """Accounts matching the identifier. Only a mobile number can match several (one per school)."""
    kind = detect_kind(identifier)
    try:
        if kind == "email":
            condition = User.email == normalize_email(identifier)
        elif kind == "phone":
            condition = User.phone == normalize_phone(identifier)
        else:
            condition = User.username == identifier.strip().lower()
    except ValueError:
        return []
    return list((await db.scalars(select(User).where(condition).limit(10))).all())


@router.get("/options", response_model=AuthOptions)
async def auth_options() -> AuthOptions:
    return AuthOptions(password_reset_enabled=_password_reset_enabled())


@router.post("/login", response_model=TokenResponse)
async def login(data: LoginRequest, response: Response, db: DbSession) -> TokenResponse:
    candidates = await _find_login_users(db, data.identifier)
    # Always run a hash verification so timing does not reveal whether the account exists.
    # A mobile number shared by schools is told apart by the password: exactly one must match.
    matches = [
        u
        for u in candidates
        if verify_password(data.password, u.password_hash)
        and u.is_active
        and await _school_active(db, u)
    ]
    if not candidates:
        verify_password(data.password, DUMMY_HASH)
    if len(matches) != 1:
        raise _invalid
    user = matches[0]
    _set_refresh_cookie(response, user.id, data.remember_me)
    return TokenResponse(
        access_token=create_token(user.id, "access"), user=UserOut.model_validate(user)
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    response: Response,
    db: DbSession,
    refresh_token: Annotated[str | None, Cookie()] = None,
) -> TokenResponse:
    decoded = decode_refresh_token(refresh_token) if refresh_token else None
    user = await db.get(User, decoded[0]) if decoded else None
    if decoded is None or user is None or not user.is_active or not await _school_active(db, user):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Session expired")
    _set_refresh_cookie(response, user.id, decoded[1])
    return TokenResponse(
        access_token=create_token(user.id, "access"), user=UserOut.model_validate(user)
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(response: Response) -> None:
    response.delete_cookie(REFRESH_COOKIE, path="/api/v1/auth")


@router.get("/me", response_model=UserOut)
async def me(user: CurrentUser) -> UserOut:
    return UserOut.model_validate(user)


@router.post("/change-password", status_code=status.HTTP_204_NO_CONTENT)
async def change_password(
    data: ChangePasswordRequest, db: DbSession, user: CurrentUser
) -> Response:
    if not verify_password(data.current_password, user.password_hash):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Current password is incorrect")
    if data.new_password == data.current_password:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail="New password must be different from the current password",
        )
    user.password_hash = hash_password(data.new_password)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
