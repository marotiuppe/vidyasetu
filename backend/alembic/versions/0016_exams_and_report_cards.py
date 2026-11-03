"""exams and report cards: terms, subjects, class subjects, exams, marks, grading scales and
bands, report aspects, aspect grades and term remarks

Every table carries school_id and branch_id (the grading scale is school-wide). Links to students
use (student_id, school_id) and links to branch tables use the composite keys used elsewhere, so
a row cannot point at another branch. Marks are Numeric(6, 2); percentages are never stored.

Revision ID: 0016
Revises: 0015
Create Date: 2026-11-03 20:00:00

"""

import sqlalchemy as sa
from alembic import op

revision = "0016"
down_revision = "0015"
branch_labels = None
depends_on = None


def _ts() -> list[sa.Column]:  # type: ignore[type-arg]
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "exam_terms",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("school_id", sa.Integer(), nullable=False),
        sa.Column("branch_id", sa.Integer(), nullable=False),
        sa.Column("academic_year_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=50), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("weight_percent", sa.Integer(), nullable=False),
        *_ts(),
        sa.CheckConstraint(
            "weight_percent >= 0 AND weight_percent <= 100", name="ck_exam_terms_weight"
        ),
        sa.ForeignKeyConstraint(["academic_year_id"], ["academic_years.id"]),
        sa.ForeignKeyConstraint(["branch_id", "school_id"], ["branches.id", "branches.school_id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("branch_id", "academic_year_id", "name"),
        sa.UniqueConstraint("id", "branch_id"),
    )
    op.create_index("ix_exam_terms_school_id", "exam_terms", ["school_id"])
    op.create_index("ix_exam_terms_branch_id", "exam_terms", ["branch_id"])
    op.create_index("ix_exam_terms_academic_year_id", "exam_terms", ["academic_year_id"])

    op.create_table(
        "subjects",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("school_id", sa.Integer(), nullable=False),
        sa.Column("branch_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("code", sa.String(length=20), nullable=True),
        sa.Column(
            "kind",
            sa.Enum(
                "scholastic", "co_scholastic", name="subjectkind", native_enum=False, length=20
            ),
            nullable=False,
        ),
        sa.Column("active", sa.Boolean(), nullable=False),
        *_ts(),
        sa.ForeignKeyConstraint(["branch_id", "school_id"], ["branches.id", "branches.school_id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("branch_id", "name"),
        sa.UniqueConstraint("id", "branch_id"),
    )
    op.create_index("ix_subjects_school_id", "subjects", ["school_id"])
    op.create_index("ix_subjects_branch_id", "subjects", ["branch_id"])

    op.create_table(
        "class_subjects",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("school_id", sa.Integer(), nullable=False),
        sa.Column("branch_id", sa.Integer(), nullable=False),
        sa.Column("class_id", sa.Integer(), nullable=False),
        sa.Column("subject_id", sa.Integer(), nullable=False),
        *_ts(),
        sa.ForeignKeyConstraint(["class_id", "branch_id"], ["classes.id", "classes.branch_id"]),
        sa.ForeignKeyConstraint(["subject_id", "branch_id"], ["subjects.id", "subjects.branch_id"]),
        sa.ForeignKeyConstraint(["branch_id", "school_id"], ["branches.id", "branches.school_id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("class_id", "subject_id"),
    )
    op.create_index("ix_class_subjects_school_id", "class_subjects", ["school_id"])
    op.create_index("ix_class_subjects_branch_id", "class_subjects", ["branch_id"])
    op.create_index("ix_class_subjects_class_id", "class_subjects", ["class_id"])
    op.create_index("ix_class_subjects_subject_id", "class_subjects", ["subject_id"])

    op.create_table(
        "exams",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("school_id", sa.Integer(), nullable=False),
        sa.Column("branch_id", sa.Integer(), nullable=False),
        sa.Column("term_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("max_marks", sa.Integer(), nullable=False),
        sa.Column("weight_percent", sa.Integer(), nullable=False),
        sa.Column("published", sa.Boolean(), nullable=False),
        sa.Column("locked", sa.Boolean(), nullable=False),
        *_ts(),
        sa.CheckConstraint("max_marks >= 1 AND max_marks <= 1000", name="ck_exams_max_marks"),
        sa.CheckConstraint("weight_percent >= 0 AND weight_percent <= 100", name="ck_exams_weight"),
        sa.ForeignKeyConstraint(
            ["term_id", "branch_id"], ["exam_terms.id", "exam_terms.branch_id"]
        ),
        sa.ForeignKeyConstraint(["branch_id", "school_id"], ["branches.id", "branches.school_id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("term_id", "name"),
        sa.UniqueConstraint("id", "branch_id"),
    )
    op.create_index("ix_exams_school_id", "exams", ["school_id"])
    op.create_index("ix_exams_branch_id", "exams", ["branch_id"])
    op.create_index("ix_exams_term_id", "exams", ["term_id"])

    op.create_table(
        "exam_marks",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("school_id", sa.Integer(), nullable=False),
        sa.Column("branch_id", sa.Integer(), nullable=False),
        sa.Column("exam_id", sa.Integer(), nullable=False),
        sa.Column("student_id", sa.Integer(), nullable=False),
        sa.Column("subject_id", sa.Integer(), nullable=False),
        sa.Column("marks", sa.Numeric(precision=6, scale=2), nullable=True),
        sa.Column("absent", sa.Boolean(), nullable=False),
        sa.Column("entered_by", sa.Integer(), nullable=False),
        *_ts(),
        sa.ForeignKeyConstraint(["exam_id", "branch_id"], ["exams.id", "exams.branch_id"]),
        sa.ForeignKeyConstraint(["student_id", "school_id"], ["students.id", "students.school_id"]),
        sa.ForeignKeyConstraint(["subject_id", "branch_id"], ["subjects.id", "subjects.branch_id"]),
        sa.ForeignKeyConstraint(["branch_id", "school_id"], ["branches.id", "branches.school_id"]),
        sa.ForeignKeyConstraint(["entered_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("exam_id", "student_id", "subject_id"),
    )
    op.create_index("ix_exam_marks_school_id", "exam_marks", ["school_id"])
    op.create_index("ix_exam_marks_branch_id", "exam_marks", ["branch_id"])
    op.create_index("ix_exam_marks_exam_id", "exam_marks", ["exam_id"])
    op.create_index("ix_exam_marks_student_id", "exam_marks", ["student_id"])
    op.create_index("ix_exam_marks_subject_id", "exam_marks", ["subject_id"])

    op.create_table(
        "grade_scales",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("school_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=50), nullable=False),
        sa.Column("is_default", sa.Boolean(), nullable=False),
        sa.Column("pass_percent", sa.Integer(), nullable=False),
        *_ts(),
        sa.CheckConstraint(
            "pass_percent >= 0 AND pass_percent <= 100", name="ck_grade_scales_pass"
        ),
        sa.ForeignKeyConstraint(["school_id"], ["schools.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("school_id", "name"),
    )
    op.create_index("ix_grade_scales_school_id", "grade_scales", ["school_id"])
    op.create_index(
        "uq_grade_scales_one_default",
        "grade_scales",
        ["school_id"],
        unique=True,
        sqlite_where=sa.text("is_default"),
        postgresql_where=sa.text("is_default"),
    )

    op.create_table(
        "grade_bands",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("scale_id", sa.Integer(), nullable=False),
        sa.Column("min_percent", sa.Integer(), nullable=False),
        sa.Column("grade", sa.String(length=10), nullable=False),
        sa.Column("grade_point", sa.Numeric(precision=4, scale=1), nullable=True),
        sa.Column("remark", sa.String(length=60), nullable=True),
        sa.CheckConstraint("min_percent >= 0 AND min_percent <= 100", name="ck_grade_bands_min"),
        sa.ForeignKeyConstraint(["scale_id"], ["grade_scales.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("scale_id", "min_percent"),
    )
    op.create_index("ix_grade_bands_scale_id", "grade_bands", ["scale_id"])

    op.create_table(
        "report_aspects",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("school_id", sa.Integer(), nullable=False),
        sa.Column("branch_id", sa.Integer(), nullable=False),
        sa.Column(
            "section",
            sa.Enum(
                "co_curricular",
                "behavioural",
                "self_awareness",
                "health",
                name="aspectsection",
                native_enum=False,
                length=20,
            ),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        *_ts(),
        sa.ForeignKeyConstraint(["branch_id", "school_id"], ["branches.id", "branches.school_id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("branch_id", "section", "name"),
        sa.UniqueConstraint("id", "branch_id"),
    )
    op.create_index("ix_report_aspects_school_id", "report_aspects", ["school_id"])
    op.create_index("ix_report_aspects_branch_id", "report_aspects", ["branch_id"])

    op.create_table(
        "aspect_grades",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("school_id", sa.Integer(), nullable=False),
        sa.Column("branch_id", sa.Integer(), nullable=False),
        sa.Column("term_id", sa.Integer(), nullable=False),
        sa.Column("student_id", sa.Integer(), nullable=False),
        sa.Column("aspect_id", sa.Integer(), nullable=False),
        sa.Column(
            "grade",
            sa.Enum("A", "B", "C", "D", "E", name="aspectgradevalue", native_enum=False, length=1),
            nullable=False,
        ),
        sa.Column("remark", sa.String(length=200), nullable=True),
        sa.Column("entered_by", sa.Integer(), nullable=False),
        *_ts(),
        sa.ForeignKeyConstraint(
            ["term_id", "branch_id"], ["exam_terms.id", "exam_terms.branch_id"]
        ),
        sa.ForeignKeyConstraint(
            ["aspect_id", "branch_id"], ["report_aspects.id", "report_aspects.branch_id"]
        ),
        sa.ForeignKeyConstraint(["student_id", "school_id"], ["students.id", "students.school_id"]),
        sa.ForeignKeyConstraint(["branch_id", "school_id"], ["branches.id", "branches.school_id"]),
        sa.ForeignKeyConstraint(["entered_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("term_id", "student_id", "aspect_id"),
    )
    op.create_index("ix_aspect_grades_school_id", "aspect_grades", ["school_id"])
    op.create_index("ix_aspect_grades_branch_id", "aspect_grades", ["branch_id"])
    op.create_index("ix_aspect_grades_term_id", "aspect_grades", ["term_id"])
    op.create_index("ix_aspect_grades_student_id", "aspect_grades", ["student_id"])
    op.create_index("ix_aspect_grades_aspect_id", "aspect_grades", ["aspect_id"])

    op.create_table(
        "term_remarks",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("school_id", sa.Integer(), nullable=False),
        sa.Column("branch_id", sa.Integer(), nullable=False),
        sa.Column("term_id", sa.Integer(), nullable=False),
        sa.Column("student_id", sa.Integer(), nullable=False),
        sa.Column("remark", sa.Text(), nullable=True),
        sa.Column("entered_by", sa.Integer(), nullable=False),
        *_ts(),
        sa.ForeignKeyConstraint(
            ["term_id", "branch_id"], ["exam_terms.id", "exam_terms.branch_id"]
        ),
        sa.ForeignKeyConstraint(["student_id", "school_id"], ["students.id", "students.school_id"]),
        sa.ForeignKeyConstraint(["branch_id", "school_id"], ["branches.id", "branches.school_id"]),
        sa.ForeignKeyConstraint(["entered_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("term_id", "student_id"),
    )
    op.create_index("ix_term_remarks_school_id", "term_remarks", ["school_id"])
    op.create_index("ix_term_remarks_branch_id", "term_remarks", ["branch_id"])
    op.create_index("ix_term_remarks_term_id", "term_remarks", ["term_id"])
    op.create_index("ix_term_remarks_student_id", "term_remarks", ["student_id"])


def downgrade() -> None:
    op.drop_index("ix_term_remarks_student_id", table_name="term_remarks")
    op.drop_index("ix_term_remarks_term_id", table_name="term_remarks")
    op.drop_index("ix_term_remarks_branch_id", table_name="term_remarks")
    op.drop_index("ix_term_remarks_school_id", table_name="term_remarks")
    op.drop_table("term_remarks")

    op.drop_index("ix_aspect_grades_aspect_id", table_name="aspect_grades")
    op.drop_index("ix_aspect_grades_student_id", table_name="aspect_grades")
    op.drop_index("ix_aspect_grades_term_id", table_name="aspect_grades")
    op.drop_index("ix_aspect_grades_branch_id", table_name="aspect_grades")
    op.drop_index("ix_aspect_grades_school_id", table_name="aspect_grades")
    op.drop_table("aspect_grades")

    op.drop_index("ix_report_aspects_branch_id", table_name="report_aspects")
    op.drop_index("ix_report_aspects_school_id", table_name="report_aspects")
    op.drop_table("report_aspects")

    op.drop_index("ix_grade_bands_scale_id", table_name="grade_bands")
    op.drop_table("grade_bands")

    op.drop_index("uq_grade_scales_one_default", table_name="grade_scales")
    op.drop_index("ix_grade_scales_school_id", table_name="grade_scales")
    op.drop_table("grade_scales")

    op.drop_index("ix_exam_marks_subject_id", table_name="exam_marks")
    op.drop_index("ix_exam_marks_student_id", table_name="exam_marks")
    op.drop_index("ix_exam_marks_exam_id", table_name="exam_marks")
    op.drop_index("ix_exam_marks_branch_id", table_name="exam_marks")
    op.drop_index("ix_exam_marks_school_id", table_name="exam_marks")
    op.drop_table("exam_marks")

    op.drop_index("ix_exams_term_id", table_name="exams")
    op.drop_index("ix_exams_branch_id", table_name="exams")
    op.drop_index("ix_exams_school_id", table_name="exams")
    op.drop_table("exams")

    op.drop_index("ix_class_subjects_subject_id", table_name="class_subjects")
    op.drop_index("ix_class_subjects_class_id", table_name="class_subjects")
    op.drop_index("ix_class_subjects_branch_id", table_name="class_subjects")
    op.drop_index("ix_class_subjects_school_id", table_name="class_subjects")
    op.drop_table("class_subjects")

    op.drop_index("ix_subjects_branch_id", table_name="subjects")
    op.drop_index("ix_subjects_school_id", table_name="subjects")
    op.drop_table("subjects")

    op.drop_index("ix_exam_terms_academic_year_id", table_name="exam_terms")
    op.drop_index("ix_exam_terms_branch_id", table_name="exam_terms")
    op.drop_index("ix_exam_terms_school_id", table_name="exam_terms")
    op.drop_table("exam_terms")
