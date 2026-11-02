from datetime import UTC, datetime, timedelta
from typing import Any, Literal

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

from app.core.config import get_settings

_hasher = PasswordHasher()
# Used to keep login timing similar when the email does not exist.
DUMMY_HASH = _hasher.hash("not-a-real-password")

TokenType = Literal["access", "refresh"]
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
    delta = (
        timedelta(minutes=settings.access_token_minutes)
        if token_type == "access"
        else timedelta(days=settings.refresh_token_days)
    )
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


def decode_token(token: str, expected: TokenType) -> int | None:
    """Return the user id if the token is valid and of the expected type."""
    data = _decode(token, expected)
    if data is None:
        return None
    try:
        return int(data["sub"])
    except (KeyError, ValueError, TypeError):
        return None


def decode_refresh_token(token: str) -> tuple[int, bool] | None:
    """Return (user id, remember_me) for a valid refresh token.

    Refresh tokens issued before the ``rem`` claim existed count as remembered.
    """
    data = _decode(token, "refresh")
    if data is None:
        return None
    try:
        user_id = int(data["sub"])
    except (KeyError, ValueError, TypeError):
        return None
    return user_id, data.get("rem", True) is True
