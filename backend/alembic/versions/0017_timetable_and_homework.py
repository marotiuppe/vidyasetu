"""timetable and homework: period slots, timetable entries, homework

Every table carries school_id and branch_id. Sections get a unique (id, branch_id) key so the new
tables can point at them with a composite key and never cross branches.

Revision ID: 0017
Revises: 0016
Create Date: 2026-11-04 10:00:00

"""

import sqlalchemy as sa
from alembic import op

revision = "0017"
down_revision = "0016"
branch_labels = None
depends_on = None


def _ts() -> list[sa.Column]:  # type: ignore[type-arg]
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    ]


def upgrade() -> None:
    with op.batch_alter_table("sections") as batch_op:
        batch_op.create_unique_constraint("uq_sections_id_branch_id", ["id", "branch_id"])

    op.create_table(
        "period_slots",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("school_id", sa.Integer(), nullable=False),
        sa.Column("branch_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=50), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("start_time", sa.Time(), nullable=False),
        sa.Column("end_time", sa.Time(), nullable=False),
        sa.Column("is_break", sa.Boolean(), nullable=False),
        *_ts(),
        sa.CheckConstraint("end_time > start_time", name="ck_period_slots_times"),
        sa.ForeignKeyConstraint(["branch_id", "school_id"], ["branches.id", "branches.school_id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("branch_id", "sequence"),
        sa.UniqueConstraint("id", "branch_id"),
    )
    op.create_index("ix_period_slots_school_id", "period_slots", ["school_id"])
    op.create_index("ix_period_slots_branch_id", "period_slots", ["branch_id"])

    op.create_table(
        "timetable_entries",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("school_id", sa.Integer(), nullable=False),
        sa.Column("branch_id", sa.Integer(), nullable=False),
        sa.Column("academic_year_id", sa.Integer(), nullable=False),
        sa.Column("section_id", sa.Integer(), nullable=False),
        sa.Column("weekday", sa.Integer(), nullable=False),
        sa.Column("period_id", sa.Integer(), nullable=False),
        sa.Column("subject_id", sa.Integer(), nullable=False),
        sa.Column("teacher_id", sa.Integer(), nullable=True),
        sa.Column("room", sa.String(length=30), nullable=True),
        *_ts(),
        sa.CheckConstraint("weekday >= 1 AND weekday <= 7", name="ck_timetable_entries_weekday"),
        sa.ForeignKeyConstraint(["academic_year_id"], ["academic_years.id"]),
        sa.ForeignKeyConstraint(["branch_id", "school_id"], ["branches.id", "branches.school_id"]),
        sa.ForeignKeyConstraint(
            ["period_id", "branch_id"], ["period_slots.id", "period_slots.branch_id"]
        ),
        sa.ForeignKeyConstraint(["section_id", "branch_id"], ["sections.id", "sections.branch_id"]),
        sa.ForeignKeyConstraint(["subject_id", "branch_id"], ["subjects.id", "subjects.branch_id"]),
        sa.ForeignKeyConstraint(["teacher_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("section_id", "academic_year_id", "weekday", "period_id"),
    )
    op.create_index("ix_timetable_entries_school_id", "timetable_entries", ["school_id"])
    op.create_index("ix_timetable_entries_branch_id", "timetable_entries", ["branch_id"])
    op.create_index(
        "ix_timetable_entries_academic_year_id", "timetable_entries", ["academic_year_id"]
    )
    op.create_index("ix_timetable_entries_section_id", "timetable_entries", ["section_id"])
    op.create_index("ix_timetable_entries_period_id", "timetable_entries", ["period_id"])
    op.create_index("ix_timetable_entries_subject_id", "timetable_entries", ["subject_id"])
    op.create_index(
        "ix_timetable_entries_teacher_slot",
        "timetable_entries",
        ["teacher_id", "academic_year_id", "weekday", "period_id"],
    )

    op.create_table(
        "homework",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("school_id", sa.Integer(), nullable=False),
        sa.Column("branch_id", sa.Integer(), nullable=False),
        sa.Column("academic_year_id", sa.Integer(), nullable=False),
        sa.Column("section_id", sa.Integer(), nullable=False),
        sa.Column("subject_id", sa.Integer(), nullable=False),
        sa.Column("teacher_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=150), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("assigned_on", sa.Date(), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=False),
        *_ts(),
        sa.CheckConstraint("due_date >= assigned_on", name="ck_homework_dates"),
        sa.ForeignKeyConstraint(["academic_year_id"], ["academic_years.id"]),
        sa.ForeignKeyConstraint(["branch_id", "school_id"], ["branches.id", "branches.school_id"]),
        sa.ForeignKeyConstraint(["section_id", "branch_id"], ["sections.id", "sections.branch_id"]),
        sa.ForeignKeyConstraint(["subject_id", "branch_id"], ["subjects.id", "subjects.branch_id"]),
        sa.ForeignKeyConstraint(["teacher_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_homework_school_id", "homework", ["school_id"])
    op.create_index("ix_homework_branch_id", "homework", ["branch_id"])
    op.create_index("ix_homework_academic_year_id", "homework", ["academic_year_id"])
    op.create_index("ix_homework_section_id", "homework", ["section_id"])
    op.create_index("ix_homework_subject_id", "homework", ["subject_id"])
    op.create_index("ix_homework_teacher_id", "homework", ["teacher_id"])
    op.create_index("ix_homework_section_due", "homework", ["section_id", "due_date"])


def downgrade() -> None:
    op.drop_table("homework")
    op.drop_table("timetable_entries")
    op.drop_table("period_slots")
    with op.batch_alter_table("sections") as batch_op:
        batch_op.drop_constraint("uq_sections_id_branch_id", type_="unique")
