"""settings: platform, school and branch settings, user preferences

The school columns login_max_attempts and login_lockout_minutes are legacy: the values now live in
the settings table. They are kept (not dropped) and no longer read.

Revision ID: 0011
Revises: 0010
Create Date: 2026-11-02 21:00:00

"""

from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "settings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("level", sa.String(length=10), nullable=False),
        sa.Column("school_id", sa.Integer(), nullable=True),
        sa.Column("branch_id", sa.Integer(), nullable=True),
        sa.Column("scope", sa.String(length=30), nullable=False),
        sa.Column("key", sa.String(length=100), nullable=False),
        sa.Column("value", sa.JSON(), nullable=False),
        sa.Column("is_secret", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("updated_by", sa.Integer(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["school_id"], ["schools.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["branch_id"], ["branches.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["updated_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("scope", "key", name="uq_settings_scope_key"),
    )
    op.create_index("ix_settings_school_id", "settings", ["school_id"])

    op.create_table(
        "user_preferences",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("key", sa.String(length=100), nullable=False),
        sa.Column("value", sa.JSON(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "key", name="uq_user_preferences_user_key"),
    )
    op.create_index("ix_user_preferences_user_id", "user_preferences", ["user_id"])

    # Carry over lockout values that differ from the built-in defaults (3 attempts, 60 minutes).
    bind = op.get_bind()
    schools = sa.table(
        "schools",
        sa.column("id", sa.Integer),
        sa.column("login_max_attempts", sa.Integer),
        sa.column("login_lockout_minutes", sa.Integer),
    )
    settings = sa.table(
        "settings",
        sa.column("level", sa.String),
        sa.column("school_id", sa.Integer),
        sa.column("scope", sa.String),
        sa.column("key", sa.String),
        sa.column("value", sa.JSON),
        sa.column("is_secret", sa.Boolean),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )
    now = datetime.now(UTC)
    rows = []
    for sid, attempts, minutes in bind.execute(
        sa.select(schools.c.id, schools.c.login_max_attempts, schools.c.login_lockout_minutes)
    ):
        for key, value, default in (
            ("security.login_max_attempts", attempts, 3),
            ("security.login_lockout_minutes", minutes, 60),
        ):
            if value is not None and value != default:
                rows.append(
                    {
                        "level": "school",
                        "school_id": sid,
                        "scope": f"s:{sid}",
                        "key": key,
                        "value": value,
                        "is_secret": False,
                        "updated_at": now,
                    }
                )
    if rows:
        op.bulk_insert(settings, rows)


def downgrade() -> None:
    op.drop_index("ix_user_preferences_user_id", table_name="user_preferences")
    op.drop_table("user_preferences")
    op.drop_index("ix_settings_school_id", table_name="settings")
    op.drop_table("settings")
