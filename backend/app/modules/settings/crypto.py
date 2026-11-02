"""Encryption of secret settings (Fernet, key derived from SETTINGS_ENCRYPTION_KEY)."""

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import get_settings


class SecretsUnavailableError(Exception):
    """No encryption key is configured, so secrets cannot be stored."""


def _fernet() -> Fernet:
    s = get_settings()
    material = s.settings_encryption_key
    if not material:
        if s.is_production:
            raise SecretsUnavailableError
        material = s.secret_key  # development convenience only
    key = base64.urlsafe_b64encode(hashlib.sha256(material.encode()).digest())
    return Fernet(key)


def encrypt(plain: str) -> str:
    return _fernet().encrypt(plain.encode()).decode()


def decrypt(token: str) -> str | None:
    """The plain text, or None when the token cannot be read (key changed or lost)."""
    try:
        return _fernet().decrypt(token.encode()).decode()
    except (InvalidToken, SecretsUnavailableError):
        return None
