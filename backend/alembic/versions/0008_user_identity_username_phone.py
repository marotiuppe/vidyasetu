"""user identity: username, optional email, unique mobile number

Revision ID: 0008
Revises: 0007
Create Date: 2026-11-02 14:00:00

"""

import re

import sqlalchemy as sa
from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None

# Kept self-contained (the app's helpers may change after this migration has shipped).
_USERNAME_RE = re.compile(r"[a-z0-9._-]{3,50}")
_MOBILE_LIKE_RE = re.compile(r"[0-9]{10,}")
_SEPARATORS_RE = re.compile(r"[\s\-()\[\]]")
_PHONE_RE = re.compile(r"[0-9]{10,15}")

users = sa.table(
    "users",
    sa.column("id", sa.Integer),
    sa.column("email", sa.String),
    sa.column("phone", sa.String),
    sa.column("username", sa.String),
)


def _valid_username(value: str) -> bool:
    if _USERNAME_RE.fullmatch(value) is None:
        return False
    if _MOBILE_LIKE_RE.fullmatch(value.replace(".", "").replace("-", "").replace("_", "")):
        return False
    return re.search(r"[a-z]", value) is not None


def _username_from_email(email: str) -> str:
    local = email.strip().lower().split("@", 1)[0]
    return re.sub(r"[^a-z0-9._-]", ".", local)[:50]


def _normalize_phone(raw: str) -> str | None:
    cleaned = _SEPARATORS_RE.sub("", raw)
    if cleaned.startswith("+"):
        return cleaned if _PHONE_RE.fullmatch(cleaned[1:]) else None
    if cleaned.isascii() and cleaned.isdigit():
        if len(cleaned) == 10:
            return "+91" + cleaned
        if len(cleaned) == 12 and cleaned.startswith("91"):
            return "+" + cleaned
    return None


def _backfill_usernames() -> None:
    bind = op.get_bind()
    rows = bind.execute(sa.select(users.c.id, users.c.email).order_by(users.c.id)).all()
    taken: set[str] = set()
    for row in rows:
        candidate = _username_from_email(row.email or "")
        if not _valid_username(candidate) or candidate in taken:
            candidate = f"user{row.id}"
            n = 1
            while candidate in taken:
                candidate = f"user{row.id}x{n}"
                n += 1
        taken.add(candidate)
        bind.execute(users.update().where(users.c.id == row.id).values(username=candidate))


def _clean_phones() -> None:
    """Normalise stored mobiles; blank ones and later duplicates become NULL.

    A value that cannot be normalised is kept as typed, so no data is lost; an admin can
    correct it through the users API.
    """
    bind = op.get_bind()
    rows = bind.execute(
        sa.select(users.c.id, users.c.phone).where(users.c.phone.is_not(None)).order_by(users.c.id)
    ).all()
    seen: set[str] = set()
    for row in rows:
        raw = row.phone.strip()
        value = _normalize_phone(raw) or raw
        new_value: str | None
        if not value or value in seen:
            new_value = None
        else:
            seen.add(value)
            new_value = value
        if new_value != row.phone:
            bind.execute(users.update().where(users.c.id == row.id).values(phone=new_value))


def upgrade() -> None:
    op.add_column("users", sa.Column("username", sa.String(length=50), nullable=True))
    # Emails are stored lower-case from now on (login compares against the stored value).
    op.execute(sa.text("UPDATE users SET email = lower(email) WHERE email IS NOT NULL"))
    _backfill_usernames()
    _clean_phones()
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.alter_column("username", existing_type=sa.String(length=50), nullable=False)
        batch_op.alter_column("email", existing_type=sa.String(length=254), nullable=True)
        batch_op.create_index("ix_users_username", ["username"], unique=True)
        batch_op.create_index("ix_users_phone", ["phone"], unique=True)


def downgrade() -> None:
    bind = op.get_bind()
    # Accounts without an email get a placeholder so the old NOT NULL column can return.
    missing = bind.execute(
        sa.select(users.c.id, users.c.username).where(users.c.email.is_(None))
    ).all()
    for row in missing:
        bind.execute(
            users.update().where(users.c.id == row.id).values(email=f"{row.username}@example.com")
        )
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.drop_index("ix_users_phone")
        batch_op.drop_index("ix_users_username")
        batch_op.alter_column("email", existing_type=sa.String(length=254), nullable=False)
        batch_op.drop_column("username")
