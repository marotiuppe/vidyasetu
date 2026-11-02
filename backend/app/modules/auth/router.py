from typing import Annotated

from fastapi import APIRouter, Cookie, HTTPException, Response, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select

from app.core.config import get_settings
from app.core.deps import CurrentUser, DbSession
from app.core.security import (
    DUMMY_HASH,
    create_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.modules.schools.models import School
from app.modules.users.models import User
from app.modules.users.schemas import UserOut

router = APIRouter(prefix="/auth", tags=["auth"])

REFRESH_COOKIE = "refresh_token"
_invalid = HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(max_length=128)
    new_password: str = Field(min_length=8, max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


def _set_refresh_cookie(response: Response, user_id: int) -> None:
    settings = get_settings()
    response.set_cookie(
        REFRESH_COOKIE,
        create_token(user_id, "refresh"),
        max_age=settings.refresh_token_days * 86400,
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


@router.post("/login", response_model=TokenResponse)
async def login(data: LoginRequest, response: Response, db: DbSession) -> TokenResponse:
    user = await db.scalar(select(User).where(User.email == data.email.lower()))
    # Always run a hash verification so timing does not reveal whether the email exists.
    ok = verify_password(data.password, user.password_hash if user else DUMMY_HASH)
    if user is None or not ok or not user.is_active or not await _school_active(db, user):
        raise _invalid
    _set_refresh_cookie(response, user.id)
    return TokenResponse(
        access_token=create_token(user.id, "access"), user=UserOut.model_validate(user)
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    response: Response,
    db: DbSession,
    refresh_token: Annotated[str | None, Cookie()] = None,
) -> TokenResponse:
    user_id = decode_token(refresh_token, "refresh") if refresh_token else None
    user = await db.get(User, user_id) if user_id else None
    if user is None or not user.is_active or not await _school_active(db, user):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Session expired")
    _set_refresh_cookie(response, user.id)
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
