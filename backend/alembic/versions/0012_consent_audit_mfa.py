"""consent, audit log, data rights and two-factor sign-in

Revision ID: 0012
Revises: 0011
Create Date: 2026-11-02 22:00:00

"""

import sqlalchemy as sa
from alembic import op

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("mfa_enabled", sa.Boolean(), nullable=False, server_default=sa.false())
        )
        batch_op.add_column(
            sa.Column("mfa_secret_encrypted", sa.String(length=500), nullable=True)
        )
        batch_op.add_column(sa.Column("mfa_last_step", sa.Integer(), nullable=True))

    op.create_table(
        "mfa_recovery_codes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("code_hash", sa.String(length=255), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_mfa_recovery_codes_user_id", "mfa_recovery_codes", ["user_id"])

    op.create_table(
        "audit_log",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("school_id", sa.Integer(), nullable=True),
        sa.Column("branch_id", sa.Integer(), nullable=True),
        sa.Column("actor_user_id", sa.Integer(), nullable=True),
        sa.Column("actor_role", sa.String(length=20), nullable=True),
        sa.Column("action", sa.String(length=50), nullable=False),
        sa.Column("entity_type", sa.String(length=30), nullable=True),
        sa.Column("entity_id", sa.String(length=40), nullable=True),
        sa.Column("outcome", sa.String(length=10), nullable=False),
        sa.Column("ip", sa.String(length=64), nullable=True),
        sa.Column("request_id", sa.String(length=40), nullable=True),
        sa.Column("detail", sa.JSON(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_audit_log_at", "audit_log", ["at"])
    op.create_index("ix_audit_log_action", "audit_log", ["action"])
    op.create_index("ix_audit_log_school_at", "audit_log", ["school_id", "at"])
    op.create_index("ix_audit_log_branch_at", "audit_log", ["branch_id", "at"])
    op.create_index("ix_audit_log_actor_at", "audit_log", ["actor_user_id", "at"])

    op.create_table(
        "policy_acceptances",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("policy", sa.String(length=20), nullable=False),
        sa.Column("version", sa.String(length=20), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ip", sa.String(length=64), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "policy", "version"),
    )
    op.create_index("ix_policy_acceptances_user_id", "policy_acceptances", ["user_id"])

    op.create_table(
        "guardian_consents",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("school_id", sa.Integer(), nullable=False),
        sa.Column("branch_id", sa.Integer(), nullable=False),
        sa.Column("student_id", sa.Integer(), nullable=False),
        sa.Column("purpose", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("given_by_user_id", sa.Integer(), nullable=True),
        sa.Column("recorded_by_user_id", sa.Integer(), nullable=False),
        sa.Column("method", sa.String(length=20), nullable=False),
        sa.Column("note", sa.String(length=200), nullable=True),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["student_id", "branch_id"], ["students.id", "students.branch_id"]
        ),
        sa.ForeignKeyConstraint(
            ["branch_id", "school_id"], ["branches.id", "branches.school_id"]
        ),
        sa.ForeignKeyConstraint(["given_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["recorded_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_guardian_consents_school_id", "guardian_consents", ["school_id"])
    op.create_index(
        "ix_guardian_consents_student_purpose",
        "guardian_consents",
        ["student_id", "purpose", "id"],
    )

    op.create_table(
        "data_requests",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("school_id", sa.Integer(), nullable=True),
        sa.Column("branch_id", sa.Integer(), nullable=True),
        sa.Column("requester_user_id", sa.Integer(), nullable=False),
        sa.Column("student_id", sa.Integer(), nullable=True),
        sa.Column("type", sa.String(length=20), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("response_note", sa.Text(), nullable=True),
        sa.Column("handled_by_user_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("due_on", sa.Date(), nullable=False),
        sa.ForeignKeyConstraint(["school_id"], ["schools.id"]),
        sa.ForeignKeyConstraint(
            ["student_id", "school_id"], ["students.id", "students.school_id"]
        ),
        sa.ForeignKeyConstraint(["requester_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["handled_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_data_requests_branch_id", "data_requests", ["branch_id"])
    op.create_index("ix_data_requests_requester_user_id", "data_requests", ["requester_user_id"])
    op.create_index("ix_data_requests_school_status", "data_requests", ["school_id", "status"])

    if op.get_bind().dialect.name == "postgresql":
        # The audit trail cannot be edited or erased, not even through direct SQL by the app role.
        op.execute(
            """
            CREATE FUNCTION audit_log_append_only() RETURNS trigger AS $$
            BEGIN
                RAISE EXCEPTION 'audit_log is append-only';
            END;
            $$ LANGUAGE plpgsql
            """
        )
        op.execute(
            """
            CREATE TRIGGER audit_log_no_change BEFORE UPDATE OR DELETE ON audit_log
            FOR EACH ROW EXECUTE FUNCTION audit_log_append_only()
            """
        )
        op.execute(
            """
            CREATE FUNCTION guardian_consents_append_only() RETURNS trigger AS $$
            BEGIN
                RAISE EXCEPTION 'guardian_consents is append-only';
            END;
            $$ LANGUAGE plpgsql
            """
        )
        op.execute(
            """
            CREATE TRIGGER guardian_consents_no_update BEFORE UPDATE ON guardian_consents
            FOR EACH ROW EXECUTE FUNCTION guardian_consents_append_only()
            """
        )


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute("DROP TRIGGER IF EXISTS guardian_consents_no_update ON guardian_consents")
        op.execute("DROP FUNCTION IF EXISTS guardian_consents_append_only()")
        op.execute("DROP TRIGGER IF EXISTS audit_log_no_change ON audit_log")
        op.execute("DROP FUNCTION IF EXISTS audit_log_append_only()")
    op.drop_table("data_requests")
    op.drop_table("guardian_consents")
    op.drop_table("policy_acceptances")
    op.drop_table("audit_log")
    op.drop_table("mfa_recovery_codes")
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.drop_column("mfa_last_step")
        batch_op.drop_column("mfa_secret_encrypted")
        batch_op.drop_column("mfa_enabled")
