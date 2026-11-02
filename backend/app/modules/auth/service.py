"""Sign-in, account lockout and server-side refresh-token sessions."""

import secrets
from dataclasses import dataclass
from datetime import timedelta
from typing import Any, cast

from sqlalchemy import and_, delete, or_, select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import (
    DUMMY_HASH,
    create_token,
    decode_refresh_token,
    verify_password,
)
from app.db.base import as_utc, utcnow
from app.modules.audit import service as audit
from app.modules.auth import mfa
from app.modules.auth.models import RefreshToken
from app.modules.schools.models import School
from app.modules.settings import service as settings_service
from app.modules.users.identity import detect_kind, normalize_email, normalize_phone
from app.modules.users.models import Role, User

# Old refresh rows are removed this long after they expired or were revoked.
_RETENTION = timedelta(days=30)


@dataclass(frozen=True)
class Session:
    user: User
    access_token: str
    refresh_token: str
    remember_me: bool
    lifetime: timedelta


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


async def _school_active(db: AsyncSession, user: User) -> bool:
    if user.school_id is None:
        return True
    school = await db.get(School, user.school_id)
    return school is not None and school.is_active


async def _login_allowed(db: AsyncSession, user: User) -> bool:
    """Active account in an active school; students only while the school allows student logins."""
    if not user.is_active or not await _school_active(db, user):
        return False
    if user.role == Role.STUDENT:
        return await settings_service.student_logins_enabled(db, user.school_id)
    return True


async def _lockout_limits(db: AsyncSession, user: User) -> tuple[int, int]:
    """(max failed attempts, lockout minutes): school setting bounded by the platform limits."""
    return await settings_service.lockout_limits(db, user.school_id)


async def register_failure(db: AsyncSession, user: User) -> bool:
    """Count a failed attempt against the account; True when this attempt locked it."""
    user.failed_login_count += 1
    max_attempts, minutes = await _lockout_limits(db, user)
    if user.failed_login_count >= max_attempts:
        user.locked_until = utcnow() + timedelta(minutes=minutes)
        user.failed_login_count = 0
        return True
    return False


async def _audit_failure(db: AsyncSession, user: User | None, reason: str, locked: bool) -> None:
    await audit.record(
        db, user, "auth.login_failed", "user", user.id if user else None,
        outcome="failed", detail={"reason": reason},
    )
    if locked and user is not None:
        await audit.record(db, user, "auth.locked", "user", user.id, outcome="denied")


async def authenticate(db: AsyncSession, identifier: str, password: str) -> User | None:
    """Return the signed-in account, or None for any failure (the caller answers generically).

    A failed password counts against the account (lockout after the school's limit). A locked
    account fails even with the right password, and that failure is not counted again.
    """
    candidates = await _find_login_users(db, identifier)
    if not candidates:
        # Same work as a real check, so timing does not reveal whether the account exists.
        verify_password(password, DUMMY_HASH)
        await _audit_failure(db, None, "unknown_account", False)
        await db.commit()
        return None

    password_ok = {u.id: verify_password(password, u.password_hash) for u in candidates}
    eligible: list[User] = []
    for user in candidates:
        locked = user.is_locked
        if password_ok[user.id] and user.is_active and not locked:
            if await _login_allowed(db, user):
                eligible.append(user)

    if len(eligible) == 1:
        user = eligible[0]
        if not user.mfa_enabled:
            # With two-factor on, the counter is cleared only after the second step succeeds,
            # so wrong codes keep counting toward the lockout.
            user.failed_login_count = 0
            user.locked_until = None
        return user

    # Failure: count it against every active, unlocked account whose password was wrong.
    # With a shared mobile number and no matching password, that is every account.
    for user in candidates:
        if user in eligible:
            continue  # ambiguous shared number with the same password: not counted
        if not await _login_allowed(db, user):
            await _audit_failure(db, user, "inactive", False)
        elif user.is_locked:
            await _audit_failure(db, user, "locked", False)
        else:
            locked = await register_failure(db, user)
            await _audit_failure(db, user, "bad_password", locked)
    await db.commit()
    return None


async def _purge_old_tokens(db: AsyncSession) -> None:
    cutoff = utcnow() - _RETENTION
    await db.execute(
        delete(RefreshToken).where(
            or_(
                RefreshToken.expires_at < cutoff,
                and_(RefreshToken.revoked_at.is_not(None), RefreshToken.revoked_at < cutoff),
            )
        )
    )


async def _session_lifetime(db: AsyncSession, user: User, remember_me: bool) -> timedelta:
    """Refresh-token lifetime: short for a plain sign-in, the school's remember-me days if set."""
    if not remember_me:
        return timedelta(hours=get_settings().short_session_hours)
    return timedelta(days=await settings_service.remember_me_days(db, user.school_id))


def _new_refresh_token(
    db: AsyncSession, user: User, family_id: str, remember_me: bool, lifetime: timedelta
) -> str:
    jti = secrets.token_urlsafe(32)
    expires_at = utcnow() + lifetime
    db.add(RefreshToken(user_id=user.id, family_id=family_id, jti=jti, expires_at=expires_at))
    return create_token(
        user.id, "refresh", {"rem": remember_me, "jti": jti}, lifetime=lifetime
    )


def _access_token(user: User) -> str:
    return create_token(user.id, "access", {"tv": user.token_version})


async def start_session(db: AsyncSession, user: User, remember_me: bool) -> Session:
    """A new sign-in gets a new token family."""
    await _purge_old_tokens(db)
    family_id = secrets.token_hex(16)
    lifetime = await _session_lifetime(db, user, remember_me)
    refresh = _new_refresh_token(db, user, family_id, remember_me, lifetime)
    await db.commit()
    return Session(user, _access_token(user), refresh, remember_me, lifetime)


async def _revoke_family(db: AsyncSession, family_id: str) -> None:
    await db.execute(
        update(RefreshToken)
        .where(RefreshToken.family_id == family_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=utcnow())
    )


async def rotate_session(db: AsyncSession, token: str) -> Session | None:
    """Exchange a refresh token for a new one in the same family (None when not usable).

    Presenting an already-used token means it was copied or stolen: the whole family is revoked.
    """
    claims = decode_refresh_token(token)
    if claims is None:
        return None
    row = await db.scalar(select(RefreshToken).where(RefreshToken.jti == claims.jti))
    if row is None or row.user_id != claims.user_id:
        return None
    now = utcnow()
    if as_utc(row.expires_at) <= now:
        return None
    # Conditional update: only one request can win the rotation of a given token.
    result = cast(
        CursorResult[Any],
        await db.execute(
            update(RefreshToken)
            .where(RefreshToken.jti == row.jti, RefreshToken.revoked_at.is_(None))
            .values(revoked_at=now)
            .execution_options(synchronize_session=False)
        ),
    )
    if result.rowcount != 1:
        await _revoke_family(db, row.family_id)
        await db.commit()
        return None
    user = await db.get(User, claims.user_id)
    if user is None or not await _login_allowed(db, user):
        await db.commit()
        return None
    # Rotation keeps the sign-in choice; the length follows the current policy.
    lifetime = await _session_lifetime(db, user, claims.remember_me)
    refresh = _new_refresh_token(db, user, row.family_id, claims.remember_me, lifetime)
    await db.commit()
    return Session(user, _access_token(user), refresh, claims.remember_me, lifetime)


async def end_session(db: AsyncSession, token: str) -> None:
    """Logout: revoke every token of the presented token's family."""
    claims = decode_refresh_token(token)
    if claims is None:
        return
    row = await db.scalar(select(RefreshToken.family_id).where(RefreshToken.jti == claims.jti))
    if row is not None:
        await _revoke_family(db, row)
        await db.commit()


async def revoke_user_sessions(db: AsyncSession, user: User) -> None:
    """Kill every access and refresh token of the user. The caller commits."""
    user.token_version += 1
    await db.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == user.id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=utcnow())
    )


async def complete_mfa_login(
    db: AsyncSession,
    user_id: int,
    token_version: int,
    code: str | None,
    recovery_code: str | None,
    remember_me: bool,
) -> Session | None:
    """Second sign-in step. None for any failure (the caller answers generically).

    A wrong code counts against the account lockout; a locked account fails without counting.
    """
    user = await db.get(User, user_id)
    if (
        user is None
        or not user.is_active
        or not user.mfa_enabled
        or user.token_version != token_version
        or not await _login_allowed(db, user)
    ):
        return None
    if user.is_locked:
        await _audit_failure(db, user, "locked", False)
        await db.commit()
        return None
    method = await mfa.verify_second_factor(db, user, code, recovery_code)
    if method is None:
        locked = await register_failure(db, user)
        await _audit_failure(db, user, "mfa_invalid", locked)
        await db.commit()
        return None
    user.failed_login_count = 0
    user.locked_until = None
    await audit.record(
        db, user, "auth.login_ok", "user", user.id, detail={"mfa": True, "method": method}
    )
    if method == "recovery":
        await audit.record(db, user, "mfa.recovery_code_used", "user", user.id)
    return await start_session(db, user, remember_me)
