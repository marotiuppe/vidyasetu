"""Two-factor sign-in: TOTP codes (RFC 6238) and one-time recovery codes."""

import hmac
import re
import secrets
import time
from typing import Literal

import pyotp
from fastapi import status
from sqlalchemy import delete, or_, select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ApiError
from app.core.security import hash_password, verify_password
from app.db.base import utcnow
from app.modules.auth.models import MfaRecoveryCode
from app.modules.settings import crypto
from app.modules.users.models import User

TOTP_PERIOD = 30
RECOVERY_CODE_COUNT = 10
# No I, O, 0 or 1, so codes survive being read aloud or copied by hand.
_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
_NON_ALNUM = re.compile(r"[^A-Za-z0-9]")
ISSUER = "Vidyasetu"

Method = Literal["totp", "recovery"]


def new_secret() -> str:
    return pyotp.random_base32()


def provisioning_uri(user: User, secret: str) -> str:
    return pyotp.TOTP(secret, interval=TOTP_PERIOD).provisioning_uri(
        name=user.username, issuer_name=ISSUER
    )


def encrypt_secret(secret: str) -> str:
    try:
        return crypto.encrypt(secret)
    except crypto.SecretsUnavailableError:
        raise ApiError(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Secret storage is not configured on the server",
            "secrets_unavailable",
        ) from None


def _normalise_code(code: str) -> str:
    return _NON_ALNUM.sub("", code)


async def check_totp(db: AsyncSession, user: User, code: str, *, at: float | None = None) -> bool:
    """Accept a code from the previous, current or next 30-second step, once per step.

    A step at or below the last accepted one is a replay and is refused. The caller commits.
    """
    digits = _normalise_code(code)
    if len(digits) != 6 or not digits.isdigit() or not user.mfa_secret_encrypted:
        return False
    secret = crypto.decrypt(user.mfa_secret_encrypted)
    if secret is None:
        return False
    totp = pyotp.TOTP(secret, interval=TOTP_PERIOD)
    now_step = int((time.time() if at is None else at) // TOTP_PERIOD)
    matched: int | None = None
    for step in (now_step - 1, now_step, now_step + 1):
        if hmac.compare_digest(totp.at(step * TOTP_PERIOD), digits):
            matched = step
    if matched is None:
        return False
    # Conditional update: only one request can claim a given step.
    result: CursorResult[tuple[()]] = await db.execute(  # type: ignore[assignment]
        update(User)
        .where(User.id == user.id, or_(User.mfa_last_step.is_(None), User.mfa_last_step < matched))
        .values(mfa_last_step=matched)
        .execution_options(synchronize_session=False)
    )
    if result.rowcount != 1:
        return False
    user.mfa_last_step = matched
    return True


def _format_code(raw: str) -> str:
    return f"{raw[:5]}-{raw[5:]}"


async def regenerate_recovery_codes(db: AsyncSession, user: User) -> list[str]:
    """Replace the user's recovery codes with a fresh set; the plain codes are returned once."""
    await db.execute(delete(MfaRecoveryCode).where(MfaRecoveryCode.user_id == user.id))
    codes: list[str] = []
    for _ in range(RECOVERY_CODE_COUNT):
        raw = "".join(secrets.choice(_ALPHABET) for _ in range(10))
        db.add(MfaRecoveryCode(user_id=user.id, code_hash=hash_password(raw)))
        codes.append(_format_code(raw))
    return codes


async def use_recovery_code(db: AsyncSession, user: User, code: str) -> bool:
    """Consume one recovery code. Each code works once. The caller commits."""
    raw = _normalise_code(code).upper()
    if len(raw) != 10:
        return False
    rows = await db.scalars(
        select(MfaRecoveryCode).where(
            MfaRecoveryCode.user_id == user.id, MfaRecoveryCode.used_at.is_(None)
        )
    )
    for row in rows:
        if verify_password(raw, row.code_hash):
            result: CursorResult[tuple[()]] = await db.execute(  # type: ignore[assignment]
                update(MfaRecoveryCode)
                .where(MfaRecoveryCode.id == row.id, MfaRecoveryCode.used_at.is_(None))
                .values(used_at=utcnow())
                .execution_options(synchronize_session=False)
            )
            return result.rowcount == 1
    return False


async def verify_second_factor(
    db: AsyncSession, user: User, code: str | None, recovery_code: str | None
) -> Method | None:
    """The method that matched (so the caller can tell the user), or None."""
    if code is not None and await check_totp(db, user, code):
        return "totp"
    if recovery_code is not None and await use_recovery_code(db, user, recovery_code):
        return "recovery"
    return None


async def clear_factor(db: AsyncSession, user: User) -> None:
    """Switch two-factor off for the user and drop its secret and recovery codes."""
    user.mfa_enabled = False
    user.mfa_secret_encrypted = None
    user.mfa_last_step = None
    await db.execute(delete(MfaRecoveryCode).where(MfaRecoveryCode.user_id == user.id))
