"""fee tools: concessions, fee reminders

Concessions and scholarships per student and year (applied when invoices are generated), and a
record of fee reminders. Both carry school_id and branch_id, and their student link is the
composite (student_id, school_id) like the other student history tables.

Revision ID: 0015
Revises: 0014
Create Date: 2026-11-03 18:00:00

"""

import sqlalchemy as sa
from alembic import op

revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "fee_concessions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("school_id", sa.Integer(), nullable=False),
        sa.Column("branch_id", sa.Integer(), nullable=False),
        sa.Column("student_id", sa.Integer(), nullable=False),
        sa.Column("academic_year_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column(
            "kind",
            sa.Enum("percent", "fixed", name="concessionkind", native_enum=False, length=20),
            nullable=False,
        ),
        sa.Column("value", sa.BigInteger(), nullable=False),
        sa.Column("fee_head_id", sa.Integer(), nullable=True),
        sa.Column("reason", sa.String(length=200), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["school_id"], ["schools.id"]),
        sa.ForeignKeyConstraint(["student_id", "school_id"], ["students.id", "students.school_id"]),
        sa.ForeignKeyConstraint(["branch_id", "school_id"], ["branches.id", "branches.school_id"]),
        sa.ForeignKeyConstraint(["fee_head_id", "school_id"], ["fee_heads.id", "fee_heads.school_id"]),
        sa.ForeignKeyConstraint(["academic_year_id"], ["academic_years.id"]),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("student_id", "academic_year_id", "name"),
    )
    op.create_index("ix_fee_concessions_school_id", "fee_concessions", ["school_id"])
    op.create_index("ix_fee_concessions_branch_id", "fee_concessions", ["branch_id"])
    op.create_index("ix_fee_concessions_academic_year_id", "fee_concessions", ["academic_year_id"])
    op.create_index(
        "ix_fee_concessions_school_student", "fee_concessions", ["school_id", "student_id"]
    )

    op.create_table(
        "fee_reminders",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("school_id", sa.Integer(), nullable=False),
        sa.Column("branch_id", sa.Integer(), nullable=False),
        sa.Column("student_id", sa.Integer(), nullable=False),
        sa.Column("invoice_id", sa.Integer(), nullable=True),
        sa.Column("channel", sa.String(length=20), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["school_id"], ["schools.id"]),
        sa.ForeignKeyConstraint(["student_id", "school_id"], ["students.id", "students.school_id"]),
        sa.ForeignKeyConstraint(["branch_id", "school_id"], ["branches.id", "branches.school_id"]),
        sa.ForeignKeyConstraint(["invoice_id", "student_id"], ["invoices.id", "invoices.student_id"]),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_fee_reminders_school_id", "fee_reminders", ["school_id"])
    op.create_index("ix_fee_reminders_branch_id", "fee_reminders", ["branch_id"])
    op.create_index("ix_fee_reminders_school_student", "fee_reminders", ["school_id", "student_id"])


def downgrade() -> None:
    op.drop_index("ix_fee_reminders_school_student", table_name="fee_reminders")
    op.drop_index("ix_fee_reminders_branch_id", table_name="fee_reminders")
    op.drop_index("ix_fee_reminders_school_id", table_name="fee_reminders")
    op.drop_table("fee_reminders")

    op.drop_index("ix_fee_concessions_school_student", table_name="fee_concessions")
    op.drop_index("ix_fee_concessions_academic_year_id", table_name="fee_concessions")
    op.drop_index("ix_fee_concessions_branch_id", table_name="fee_concessions")
    op.drop_index("ix_fee_concessions_school_id", table_name="fee_concessions")
    op.drop_table("fee_concessions")
