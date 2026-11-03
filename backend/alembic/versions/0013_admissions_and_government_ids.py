"""admissions (applications and documents) and student government identifiers

Revision ID: 0013
Revises: 0012
Create Date: 2026-11-03 10:00:00

"""

import sqlalchemy as sa
from alembic import op

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("students", schema=None) as batch_op:
        batch_op.add_column(sa.Column("pen", sa.String(length=11), nullable=True))
        batch_op.add_column(sa.Column("apaar_id", sa.String(length=12), nullable=True))
        batch_op.add_column(sa.Column("apaar_consent", sa.Boolean(), nullable=True))
        batch_op.add_column(sa.Column("aadhaar_details_match", sa.Boolean(), nullable=True))
    op.create_index(
        "uq_students_school_pen",
        "students",
        ["school_id", "pen"],
        unique=True,
        sqlite_where=sa.text("pen IS NOT NULL"),
        postgresql_where=sa.text("pen IS NOT NULL"),
    )

    op.create_table(
        "admission_applications",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("school_id", sa.Integer(), nullable=False),
        sa.Column("branch_id", sa.Integer(), nullable=False),
        sa.Column("first_name", sa.String(length=100), nullable=False),
        sa.Column("last_name", sa.String(length=100), nullable=False),
        sa.Column("gender", sa.String(length=20), nullable=True),
        sa.Column("date_of_birth", sa.Date(), nullable=True),
        sa.Column("class_id", sa.Integer(), nullable=True),
        sa.Column("academic_year_id", sa.Integer(), nullable=True),
        sa.Column("guardian_name", sa.String(length=200), nullable=False),
        sa.Column("guardian_phone", sa.String(length=20), nullable=False),
        sa.Column("guardian_email", sa.String(length=254), nullable=True),
        sa.Column("guardian_relation", sa.String(length=20), nullable=False),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column("previous_school", sa.String(length=200), nullable=True),
        sa.Column("source", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="enquiry", nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        sa.Column("privacy_notice_accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("student_id", sa.Integer(), nullable=True),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["school_id"], ["schools.id"]),
        sa.ForeignKeyConstraint(["academic_year_id"], ["academic_years.id"]),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.ForeignKeyConstraint(
            ["branch_id", "school_id"], ["branches.id", "branches.school_id"]
        ),
        sa.ForeignKeyConstraint(["class_id", "branch_id"], ["classes.id", "classes.branch_id"]),
        sa.ForeignKeyConstraint(
            ["student_id", "school_id"], ["students.id", "students.school_id"]
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id", "school_id", name="uq_admission_applications_id_school"),
        sa.UniqueConstraint("student_id", name="uq_admission_applications_student_id"),
    )
    op.create_index(
        "ix_admission_applications_school_id", "admission_applications", ["school_id"]
    )
    op.create_index(
        "ix_admission_applications_branch_id", "admission_applications", ["branch_id"]
    )
    op.create_index("ix_admission_applications_status", "admission_applications", ["status"])
    op.create_index(
        "ix_admission_applications_school_status",
        "admission_applications",
        ["school_id", "status"],
    )

    op.create_table(
        "admission_documents",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("school_id", sa.Integer(), nullable=False),
        sa.Column("application_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("content_type", sa.String(length=30), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("data", sa.LargeBinary(), nullable=False),
        sa.Column("uploaded_by", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["school_id"], ["schools.id"]),
        sa.ForeignKeyConstraint(["uploaded_by"], ["users.id"]),
        sa.ForeignKeyConstraint(
            ["application_id", "school_id"],
            ["admission_applications.id", "admission_applications.school_id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_admission_documents_school_id", "admission_documents", ["school_id"])
    op.create_index(
        "ix_admission_documents_application_id", "admission_documents", ["application_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_admission_documents_application_id", table_name="admission_documents")
    op.drop_index("ix_admission_documents_school_id", table_name="admission_documents")
    op.drop_table("admission_documents")

    op.drop_index("ix_admission_applications_school_status", table_name="admission_applications")
    op.drop_index("ix_admission_applications_status", table_name="admission_applications")
    op.drop_index("ix_admission_applications_branch_id", table_name="admission_applications")
    op.drop_index("ix_admission_applications_school_id", table_name="admission_applications")
    op.drop_table("admission_applications")

    op.drop_index("uq_students_school_pen", table_name="students")
    with op.batch_alter_table("students", schema=None) as batch_op:
        batch_op.drop_column("aadhaar_details_match")
        batch_op.drop_column("apaar_consent")
        batch_op.drop_column("apaar_id")
        batch_op.drop_column("pen")
