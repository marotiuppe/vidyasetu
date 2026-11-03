"""Password rules for every place that accepts a new password.

Old passwords keep working at sign-in; the policy applies only when a password is set.
"""

import re
import secrets

from app.core.errors import ApiError

MIN_LENGTH = 10
MAX_LENGTH = 128
WEAK_CODE = "weak_password"

# Very common and leaked passwords (lower case). Trailing or leading digits and symbols are
# stripped before the lookup, so "password123!" is caught as "password".
COMMON_PASSWORDS: frozenset[str] = frozenset(
    {
        "password", "passw0rd", "p@ssword", "p@ssw0rd", "pass", "pass123", "passwd",
        "password1", "password12", "password123", "password1234", "letmein", "letmein1",
        "welcome", "welcome1", "welcome123", "qwerty", "qwerty1", "qwerty12", "qwerty123",
        "qwertyuiop", "asdfgh", "asdfghjkl", "zxcvbnm", "qazwsx", "zaq12wsx", "1q2w3e4r",
        "1q2w3e4r5t", "abc123", "abcd1234", "abcdef", "abcdefgh", "a123456", "aa123456",
        "123456a", "admin", "admin123", "administrator", "root", "toor", "system", "guest",
        "default", "changeme", "change", "secret", "login", "access", "iloveyou", "iloveu",
        "loveme", "lovely", "hello", "hello123", "monkey", "monkey1", "dragon", "football",
        "football1", "baseball", "baseball1", "soccer", "hockey", "basketball", "jordan",
        "sunshine", "sunshine1", "princess", "princess1", "flower", "freedom", "whatever",
        "shadow", "master", "superman", "batman", "spiderman", "starwars", "matrix",
        "pokemon", "naruto", "computer", "internet", "mustang", "ashley", "bailey",
        "charlie", "donald", "michael", "jessica", "thomas", "robert", "daniel", "george",
        "andrew", "joshua", "hottie", "harley", "ranger", "buster", "tigger", "cookie",
        "summer", "winter", "spring", "autumn", "trustno1", "school", "school123",
        "school@123", "vidyasetu", "vidya123", "teacher", "teacher1", "student", "student1",
        "parent", "parent123", "office", "principal", "accounts", "clerk", "india",
        "india123", "bharat", "mumbai", "pune", "maharashtra", "rahul", "mahesh", "sachin",
        "ganesh", "111111", "11111111", "1111111111", "000000", "00000000", "123123",
        "121212", "123321", "654321", "666666", "696969", "123456", "1234567", "12345678",
        "123456789", "1234567890", "0123456789", "1234", "12345", "987654321",
        "00000000000", "7777777", "888888", "12341234",
    }
)

_STRIP_EDGES = re.compile(r"^[^a-z]+|[^a-z]+$")
_ALNUM = re.compile(r"[^a-z0-9]")
_SEQUENCE_SOURCES = (
    "abcdefghijklmnopqrstuvwxyz",
    "01234567890",
    "qwertyuiop",
    "asdfghjkl",
    "zxcvbnm",
)


class WeakPasswordError(ValueError):
    """Raised with a user-safe message that never includes the password."""


def _is_sequence(text: str) -> bool:
    if len(text) < 4:
        return False
    return any(text in src or text[::-1] in src for src in _SEQUENCE_SOURCES)


def password_problem(
    password: str,
    *,
    username: str | None = None,
    email: str | None = None,
    full_name: str | None = None,
    min_length: int = MIN_LENGTH,
) -> str | None:
    """Return the first rule the password breaks, or None when it is acceptable.

    `min_length` is the school's setting; it can raise the minimum but never lower it below 10.
    """
    minimum = max(MIN_LENGTH, min_length)
    if len(password) < minimum:
        return f"Password must be at least {minimum} characters"
    if len(password) > MAX_LENGTH:
        return f"Password must be at most {MAX_LENGTH} characters"
    lower = password.lower()
    stripped = _STRIP_EDGES.sub("", lower)
    if lower in COMMON_PASSWORDS or stripped in COMMON_PASSWORDS:
        return "This password is too common. Choose a less predictable password"
    if len(set(password)) == 1:
        return "Password must not be one repeated character"
    alnum = _ALNUM.sub("", lower)
    if _is_sequence(alnum) or _is_sequence(_ALNUM.sub("", stripped)):
        return "Password must not be a simple sequence such as abcdef or 12345678"
    if username and len(username) >= 3 and username.lower() in lower:
        return "Password must not contain your username"
    if email:
        local = email.lower().split("@", 1)[0]
        if len(local) >= 3 and local in lower:
            return "Password must not contain your email address"
    if full_name:
        name = re.sub(r"\s+", "", full_name).lower()
        if name and re.sub(r"\s+", "", lower) == name:
            return "Password must not be your name"
    return None


def enforce_password(
    password: str,
    *,
    username: str | None = None,
    email: str | None = None,
    full_name: str | None = None,
    min_length: int = MIN_LENGTH,
) -> None:
    """Raise 422 (code `weak_password`) when the password breaks the policy."""
    problem = password_problem(
        password, username=username, email=email, full_name=full_name, min_length=min_length
    )
    if problem is not None:
        raise ApiError(422, problem, WEAK_CODE)


# Characters for generated temporary passwords (no look-alikes: I, O, l, 0, 1).
_GEN_UPPER = "ABCDEFGHJKLMNPQRSTUVWXYZ"
_GEN_LOWER = "abcdefghijkmnopqrstuvwxyz"
_GEN_DIGIT = "23456789"
_GEN_SYMBOL = "@#$%&*"
_GEN_ALL = _GEN_UPPER + _GEN_LOWER + _GEN_DIGIT + _GEN_SYMBOL
GENERATED_LENGTH = 12


def random_password(
    username: str, full_name: str, *, length: int = GENERATED_LENGTH, min_length: int = 0
) -> str:
    """A random temporary password that passes the password policy.

    `length` is the default size; `min_length` is the school's minimum (the larger one wins).
    """
    size = max(length, min_length, MIN_LENGTH)
    rng = secrets.SystemRandom()
    while True:
        chars = [
            secrets.choice(_GEN_UPPER),
            secrets.choice(_GEN_LOWER),
            secrets.choice(_GEN_DIGIT),
            secrets.choice(_GEN_SYMBOL),
        ]
        chars += [secrets.choice(_GEN_ALL) for _ in range(size - len(chars))]
        rng.shuffle(chars)
        password = "".join(chars)
        if password_problem(password, username=username, full_name=full_name) is None:
            return password
