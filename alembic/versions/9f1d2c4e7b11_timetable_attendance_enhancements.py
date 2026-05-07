"""timetable attendance enhancements

Revision ID: 9f1d2c4e7b11
Revises: c31b7a9f2d11
Create Date: 2026-05-07
"""

from alembic import op
import sqlalchemy as sa


revision = "9f1d2c4e7b11"
down_revision = "c31b7a9f2d11"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("teacher_timetables", sa.Column("version_no", sa.Integer(), nullable=False, server_default="1"))
    op.add_column("teacher_timetables", sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()))

    op.drop_constraint("attendance_sessions_section_id_subject_id_session_date_key", "attendance_sessions", type_="unique")
    op.create_unique_constraint(
        "uq_attendance_sessions_period_date",
        "attendance_sessions",
        ["section_id", "subject_id", "session_date", "timetable_id"],
    )

    op.add_column("attendance_sessions", sa.Column("approved_by", sa.UUID(), nullable=True))
    op.add_column("attendance_sessions", sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True))
    op.create_foreign_key(
        "fk_attendance_sessions_approved_by_users",
        "attendance_sessions",
        "users",
        ["approved_by"],
        ["id"],
    )

    op.create_table(
        "attendance_audit_logs",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("session_id", sa.UUID(), nullable=False),
        sa.Column("action", sa.String(length=50), nullable=False),
        sa.Column("actor_user_id", sa.UUID(), nullable=True),
        sa.Column("meta_json", sa.String(length=1000), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["session_id"], ["attendance_sessions.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_attendance_audit_logs_session_id"), "attendance_audit_logs", ["session_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_attendance_audit_logs_session_id"), table_name="attendance_audit_logs")
    op.drop_table("attendance_audit_logs")

    op.drop_constraint("fk_attendance_sessions_approved_by_users", "attendance_sessions", type_="foreignkey")
    op.drop_column("attendance_sessions", "approved_at")
    op.drop_column("attendance_sessions", "approved_by")

    op.drop_constraint("uq_attendance_sessions_period_date", "attendance_sessions", type_="unique")
    op.create_unique_constraint(
        "attendance_sessions_section_id_subject_id_session_date_key",
        "attendance_sessions",
        ["section_id", "subject_id", "session_date"],
    )

    op.drop_column("teacher_timetables", "is_active")
    op.drop_column("teacher_timetables", "version_no")
