"""Two-factor setup for the signed-in user (the sign-in step itself is in router.py)."""

from fastapi import APIRouter, status
from pydantic import BaseModel, Field

from app.core.deps import CurrentUser, DbSession
from app.core.errors import ApiError
from app.core.security import verify_password
from app.modules.audit import service as audit
from app.modules.auth import mfa
from app.modules.auth import service as auth_service
from app.modules.settings import service as settings_service
from app.modules.users.models import User

router = APIRouter(prefix="/auth/mfa", tags=["auth"])


class PasswordBody(BaseModel):
    password: str = Field(min_length=1, max_length=128)


class SetupOut(BaseModel):
    secret: str
    otpauth_uri: str


class CodeBody(BaseModel):
    code: str = Field(min_length=1, max_length=20)


class PasswordCodeBody(PasswordBody, CodeBody):
    pass


class RecoveryCodesOut(BaseModel):
    recovery_codes: list[str]


async def _fail(db: DbSession, user: User, reason: str, *, count: bool = True) -> ApiError:
    """A wrong password or code here counts against the lockout, like a failed sign-in.

    Not counted while enabling (a mistyped first code is harmless: nothing is protected yet).
    """
    locked = await auth_service.register_failure(db, user) if count else False
    await audit.record(
        db, user, "mfa.verify_failed", "user", user.id, outcome="failed",
        detail={"reason": reason},
    )
    if locked:
        await audit.record(db, user, "auth.locked", "user", user.id, outcome="denied")
    await db.commit()
    return ApiError(status.HTTP_400_BAD_REQUEST, "Incorrect password or code", f"invalid_{reason}")


async def _check_password(db: DbSession, user: User, password: str) -> None:
    if not verify_password(password, user.password_hash):
        raise await _fail(db, user, "password")


async def _check_code(db: DbSession, user: User, code: str) -> None:
    if not user.mfa_enabled or not await mfa.check_totp(db, user, code):
        raise await _fail(db, user, "code")


@router.post("/setup", response_model=SetupOut)
async def setup(data: PasswordBody, db: DbSession, user: CurrentUser) -> SetupOut:
    """Start setup: returns a new secret to scan or type into an authenticator app.

    Nothing changes for sign-in until `enable` succeeds. Calling this again before enabling
    replaces the pending secret.
    """
    if user.mfa_enabled:
        raise ApiError(
            status.HTTP_409_CONFLICT, "Two-factor is already on", "mfa_already_enabled"
        )
    await _check_password(db, user, data.password)
    secret = mfa.new_secret()
    user.mfa_secret_encrypted = mfa.encrypt_secret(secret)
    user.mfa_last_step = None
    await db.commit()
    return SetupOut(secret=secret, otpauth_uri=mfa.provisioning_uri(user, secret))


@router.post("/enable", response_model=RecoveryCodesOut)
async def enable(data: CodeBody, db: DbSession, user: CurrentUser) -> RecoveryCodesOut:
    if user.mfa_enabled:
        raise ApiError(
            status.HTTP_409_CONFLICT, "Two-factor is already on", "mfa_already_enabled"
        )
    if not user.mfa_secret_encrypted:
        raise ApiError(status.HTTP_409_CONFLICT, "Start the setup first", "mfa_not_started")
    if not await mfa.check_totp(db, user, data.code):
        raise await _fail(db, user, "code", count=False)
    user.mfa_enabled = True
    codes = await mfa.regenerate_recovery_codes(db, user)
    await audit.record(db, user, "mfa.enabled", "user", user.id)
    await db.commit()
    return RecoveryCodesOut(recovery_codes=codes)


@router.post("/disable", status_code=status.HTTP_204_NO_CONTENT)
async def disable(data: PasswordCodeBody, db: DbSession, user: CurrentUser) -> None:
    if await settings_service.mfa_required(db, user):
        await audit.record(
            db, user, "mfa.disabled", "user", user.id, outcome="denied",
            detail={"reason": "required_by_policy"}, commit=True,
        )
        raise ApiError(
            status.HTTP_403_FORBIDDEN,
            "Two-factor is required for your role and cannot be switched off",
            "mfa_required",
        )
    await _check_password(db, user, data.password)
    await _check_code(db, user, data.code)
    await mfa.clear_factor(db, user)
    await audit.record(db, user, "mfa.disabled", "user", user.id)
    await db.commit()


@router.post("/recovery-codes", response_model=RecoveryCodesOut)
async def new_recovery_codes(
    data: PasswordCodeBody, db: DbSession, user: CurrentUser
) -> RecoveryCodesOut:
    await _check_password(db, user, data.password)
    await _check_code(db, user, data.code)
    codes = await mfa.regenerate_recovery_codes(db, user)
    await audit.record(db, user, "mfa.recovery_codes_regenerated", "user", user.id)
    await db.commit()
    return RecoveryCodesOut(recovery_codes=codes)
