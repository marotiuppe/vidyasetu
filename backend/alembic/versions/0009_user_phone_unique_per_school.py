"""mobile number unique per school, not globally

Revision ID: 0009
Revises: 0008
Create Date: 2026-11-02 17:10:00

"""

from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.drop_index("ix_users_phone")
        batch_op.create_index("ix_users_phone", ["phone"], unique=False)
        batch_op.create_unique_constraint("uq_users_school_phone", ["school_id", "phone"])


def downgrade() -> None:
    # Fails if two schools now share a mobile number; fix those first.
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.drop_constraint("uq_users_school_phone", type_="unique")
        batch_op.drop_index("ix_users_phone")
        batch_op.create_index("ix_users_phone", ["phone"], unique=True)
