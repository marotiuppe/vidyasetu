from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

from app.core.config import get_settings

_hasher = PasswordHasher()
# Used to keep login timing similar when the email does not exist.
DUMMY_HASH = _hasher.hash("not-a-real-password")

TokenType = Literal["access", "refresh", "mfa"]
MFA_TOKEN_MINUTES = 5
ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerificationError, InvalidHashError):
        return False


def create_token(
    user_id: int, token_type: TokenType, extra_claims: dict[str, Any] | None = None
) -> str:
    settings = get_settings()
    if token_type == "access":
        delta = timedelta(minutes=settings.access_token_minutes)
    elif token_type == "mfa":
        delta = timedelta(minutes=MFA_TOKEN_MINUTES)
    else:
        delta = timedelta(days=settings.refresh_token_days)
    payload: dict[str, Any] = {**(extra_claims or {})}
    payload.update(
        {
            "sub": str(user_id),
            "type": token_type,
            "exp": datetime.now(UTC) + delta,
        }
    )
    return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)


def _decode(token: str, expected: TokenType) -> dict[str, Any] | None:
    try:
        data: dict[str, Any] = jwt.decode(token, get_settings().secret_key, algorithms=[ALGORITHM])
    except jwt.PyJWTError:
        return None
    if data.get("type") != expected:
        return None
    return data


@dataclass(frozen=True)
class AccessClaims:
    user_id: int
    # Must equal the user's token_version; bumped to kill every outstanding access token.
    token_version: int


def decode_access_token(token: str) -> AccessClaims | None:
    """Return the user id and token version of a valid access token.

    Access tokens issued before the ``tv`` claim existed count as version 0.
    """
    data = _decode(token, "access")
    if data is None:
        return None
    try:
        user_id = int(data["sub"])
        version = data.get("tv", 0)
        if not isinstance(version, int) or isinstance(version, bool):
            return None
    except (KeyError, ValueError, TypeError):
        return None
    return AccessClaims(user_id=user_id, token_version=version)


@dataclass(frozen=True)
class RefreshClaims:
    user_id: int
    remember_me: bool
    jti: str


def decode_refresh_token(token: str) -> RefreshClaims | None:
    """Return the claims of a valid refresh token.

    Tokens without a ``jti`` (issued before server-side refresh tokens) are rejected, so those
    sessions end and the user signs in again.
    """
    data = _decode(token, "refresh")
    if data is None:
        return None
    try:
        user_id = int(data["sub"])
        jti = data["jti"]
    except (KeyError, ValueError, TypeError):
        return None
    if not isinstance(jti, str) or not jti:
        return None
    return RefreshClaims(user_id=user_id, remember_me=data.get("rem", True) is True, jti=jti)


@dataclass(frozen=True)
class MfaClaims:
    user_id: int
    remember_me: bool
    token_version: int


def decode_mfa_token(token: str) -> MfaClaims | None:
    """Claims of the short-lived token issued after a correct password for an MFA account.

    It is only accepted by the second sign-in step, never as an access or refresh token.
    """
    data = _decode(token, "mfa")
    if data is None:
        return None
    try:
        user_id = int(data["sub"])
        version = data.get("tv", 0)
        if not isinstance(version, int) or isinstance(version, bool):
            return None
    except (KeyError, ValueError, TypeError):
        return None
    remember = data.get("rem", False) is True
    return MfaClaims(user_id=user_id, remember_me=remember, token_version=version)
