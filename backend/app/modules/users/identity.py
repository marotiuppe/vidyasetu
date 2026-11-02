"""Normalisation and detection of sign-in identifiers (email, mobile number, username)."""

import re
from typing import Literal

IdentifierKind = Literal["email", "phone", "username"]

_PHONE_SEPARATORS = re.compile(r"[\s\-()\[\]]")
_PHONE_RE = re.compile(r"\+?[0-9]{10,15}")
_USERNAME_RE = re.compile(r"[a-z0-9._-]{3,50}")
_MOBILE_LIKE_RE = re.compile(r"[0-9]{10,}")
_LETTER_RE = re.compile(r"[a-z]")


def normalize_email(value: str) -> str:
    return value.strip().lower()


def normalize_phone(value: str) -> str:
    """Return the mobile number in E.164-like form (``+91`` for 10-digit Indian numbers)."""
    cleaned = _PHONE_SEPARATORS.sub("", value)
    if cleaned.startswith("+"):
        if _PHONE_RE.fullmatch(cleaned):
            return cleaned
    elif cleaned.isascii() and cleaned.isdigit():
        if len(cleaned) == 10:
            return "+91" + cleaned
        if len(cleaned) == 12 and cleaned.startswith("91"):
            return "+" + cleaned
    raise ValueError("Enter a valid mobile number (10 digits, or with +91 country code)")


def normalize_username(value: str) -> str:
    username = value.strip().lower()
    if not _USERNAME_RE.fullmatch(username):
        raise ValueError(
            "Username must be 3-50 characters: letters, digits, dot, dash or underscore"
        )
    if _MOBILE_LIKE_RE.fullmatch(username.replace(".", "").replace("-", "").replace("_", "")):
        raise ValueError("Username cannot look like a mobile number")
    if _LETTER_RE.search(username) is None:
        raise ValueError("Username must contain at least one letter")
    return username


def detect_kind(identifier: str) -> IdentifierKind:
    if "@" in identifier:
        return "email"
    if _PHONE_RE.fullmatch(_PHONE_SEPARATORS.sub("", identifier.strip())):
        return "phone"
    return "username"


def suggest_username(email: str) -> str:
    """A username derived from the email's local part; not checked against existing users."""
    local = normalize_email(email).split("@", 1)[0]
    base = re.sub(r"[^a-z0-9._-]", ".", local)[:50]
    try:
        return normalize_username(base)
    except ValueError:
        return "user"
