"""year-end promotion: batches and items; student history FKs move from branch to school

Students can now change branch (promotion to the other branch). History rows (enrolments,
attendance, consents, invoices) keep the branch where they happened, so their composite FK to
students is (student_id, school_id) instead of (student_id, branch_id). Invoices also get the
balance carried forward to the next year.

Revision ID: 0014
Revises: 0013
Create Date: 2026-11-03 12:00:00

"""

import sqlalchemy as sa
from alembic import op

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None

_STUDENT_FK_TABLES = ("enrollments", "attendance_records", "guardian_consents", "invoices")
# Gives unnamed SQLite constraints the name alembic assigns while reflecting, so they can be
# dropped by name. PostgreSQL names them itself and the inspector returns those names.
_NAMING = {"fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s"}


def _find_student_fk(table: str, columns: list[str]) -> str:
    """Name of the FK from `table`(`columns`) to students, discovered with the inspector."""
    inspector = sa.inspect(op.get_bind())
    for fk in inspector.get_foreign_keys(table):
        if fk["referred_table"] == "students" and fk["constrained_columns"] == columns:
            return fk["name"] or f"fk_{table}_{columns[0]}_students"
    raise RuntimeError(f"No foreign key {columns} -> students found on {table}")


def upgrade() -> None:
    for table in _STUDENT_FK_TABLES:
        old = _find_student_fk(table, ["student_id", "branch_id"])
        with op.batch_alter_table(table, naming_convention=_NAMING) as batch_op:
            batch_op.drop_constraint(old, type_="foreignkey")
            batch_op.create_foreign_key(
                f"fk_{table}_student_school_students",
                "students",
                ["student_id", "school_id"],
                ["id", "school_id"],
            )
            if table == "invoices":
                batch_op.add_column(
                    sa.Column(
                        "carried_forward_paise",
                        sa.BigInteger(),
                        nullable=False,
                        server_default="0",
                    )
                )

    op.create_table(
        "promotion_batches",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("school_id", sa.Integer(), nullable=False),
        sa.Column("from_year_id", sa.Integer(), nullable=False),
        sa.Column("to_year_id", sa.Integer(), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("undo_until", sa.DateTime(timezone=True), nullable=False),
        sa.Column("undone_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("undone_by", sa.Integer(), nullable=True),
        sa.Column("carry_over", sa.Boolean(), nullable=False),
        sa.Column("promoted", sa.Integer(), nullable=False),
        sa.Column("detained", sa.Integer(), nullable=False),
        sa.Column("left", sa.Integer(), nullable=False),
        sa.Column("passed_out", sa.Integer(), nullable=False),
        sa.Column("transferred", sa.Integer(), nullable=False),
        sa.Column("carried_invoices", sa.Integer(), nullable=False),
        sa.Column("carried_paise", sa.BigInteger(), nullable=False),
        sa.ForeignKeyConstraint(["school_id"], ["schools.id"]),
        sa.ForeignKeyConstraint(["from_year_id"], ["academic_years.id"]),
        sa.ForeignKeyConstraint(["to_year_id"], ["academic_years.id"]),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["undone_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_promotion_batches_school_id", "promotion_batches", ["school_id"])

    op.create_table(
        "promotion_items",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("batch_id", sa.Integer(), nullable=False),
        sa.Column("school_id", sa.Integer(), nullable=False),
        sa.Column("student_id", sa.Integer(), nullable=False),
        sa.Column("action", sa.String(length=20), nullable=False),
        sa.Column("from_enrollment_id", sa.Integer(), nullable=True),
        sa.Column("to_enrollment_id", sa.Integer(), nullable=True),
        sa.Column("from_branch_id", sa.Integer(), nullable=False),
        sa.Column("to_branch_id", sa.Integer(), nullable=False),
        sa.Column("from_status", sa.String(length=20), nullable=False),
        sa.Column("to_status", sa.String(length=20), nullable=False),
        sa.Column("carry_invoice_id", sa.Integer(), nullable=True),
        sa.Column("carried_paise", sa.BigInteger(), nullable=False, server_default="0"),
        sa.ForeignKeyConstraint(["batch_id"], ["promotion_batches.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["student_id", "school_id"], ["students.id", "students.school_id"]),
        sa.ForeignKeyConstraint(["from_enrollment_id"], ["enrollments.id"]),
        sa.ForeignKeyConstraint(["to_enrollment_id"], ["enrollments.id"]),
        sa.ForeignKeyConstraint(["from_branch_id"], ["branches.id"]),
        sa.ForeignKeyConstraint(["to_branch_id"], ["branches.id"]),
        sa.ForeignKeyConstraint(["carry_invoice_id"], ["invoices.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_promotion_items_batch_id", "promotion_items", ["batch_id"])
    op.create_index("ix_promotion_items_school_id", "promotion_items", ["school_id"])
    op.create_index("ix_promotion_items_student_id", "promotion_items", ["student_id"])


def downgrade() -> None:
    bind = op.get_bind()
    for table in _STUDENT_FK_TABLES:
        moved = bind.execute(
            sa.text(
                f"SELECT COUNT(*) FROM {table} t JOIN students s ON s.id = t.student_id "
                "WHERE t.branch_id <> s.branch_id"
            )
        ).scalar()
        if moved:
            raise RuntimeError(
                f"Cannot downgrade: {moved} row(s) in {table} belong to a student who has "
                "since moved to another branch. Undo those promotions first."
            )

    op.drop_index("ix_promotion_items_student_id", table_name="promotion_items")
    op.drop_index("ix_promotion_items_school_id", table_name="promotion_items")
    op.drop_index("ix_promotion_items_batch_id", table_name="promotion_items")
    op.drop_table("promotion_items")
    op.drop_index("ix_promotion_batches_school_id", table_name="promotion_batches")
    op.drop_table("promotion_batches")

    for table in _STUDENT_FK_TABLES:
        with op.batch_alter_table(table, naming_convention=_NAMING) as batch_op:
            if table == "invoices":
                batch_op.drop_column("carried_forward_paise")
            batch_op.drop_constraint(f"fk_{table}_student_school_students", type_="foreignkey")
            batch_op.create_foreign_key(
                f"fk_{table}_student_branch_students",
                "students",
                ["student_id", "branch_id"],
                ["id", "branch_id"],
            )
