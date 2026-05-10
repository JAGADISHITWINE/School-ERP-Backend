"""add guardian email and notification logs

Revision ID: 7c2e9d8f1a33
Revises: 6b1a9c7d4e22
Create Date: 2026-05-10 14:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "7c2e9d8f1a33"
down_revision: Union[str, None] = "6b1a9c7d4e22"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


notification_channel = postgresql.ENUM("EMAIL", "SMS", name="notificationchannel", create_type=False)
notification_status = postgresql.ENUM("PENDING", "SENT", "FAILED", "SKIPPED", name="notificationstatus", create_type=False)


def upgrade() -> None:
    notification_channel.create(op.get_bind(), checkfirst=True)
    notification_status.create(op.get_bind(), checkfirst=True)

    op.add_column("students", sa.Column("guardian_email", sa.String(length=255), nullable=True))
    op.create_table(
        "notification_logs",
        sa.Column("institution_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("student_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("attendance_session_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("channel", notification_channel, nullable=False),
        sa.Column("recipient", sa.String(length=255), nullable=True),
        sa.Column("subject", sa.String(length=255), nullable=True),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("status", notification_status, nullable=False),
        sa.Column("provider", sa.String(length=50), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("dedupe_key", sa.String(length=255), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["attendance_session_id"], ["attendance_sessions.id"]),
        sa.ForeignKeyConstraint(["institution_id"], ["institutions.id"]),
        sa.ForeignKeyConstraint(["student_id"], ["students.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("dedupe_key"),
    )
    op.create_index(op.f("ix_notification_logs_attendance_session_id"), "notification_logs", ["attendance_session_id"], unique=False)
    op.create_index(op.f("ix_notification_logs_institution_id"), "notification_logs", ["institution_id"], unique=False)
    op.create_index(op.f("ix_notification_logs_status"), "notification_logs", ["status"], unique=False)
    op.create_index(op.f("ix_notification_logs_student_id"), "notification_logs", ["student_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_notification_logs_student_id"), table_name="notification_logs")
    op.drop_index(op.f("ix_notification_logs_status"), table_name="notification_logs")
    op.drop_index(op.f("ix_notification_logs_institution_id"), table_name="notification_logs")
    op.drop_index(op.f("ix_notification_logs_attendance_session_id"), table_name="notification_logs")
    op.drop_table("notification_logs")
    op.drop_column("students", "guardian_email")
    notification_status.drop(op.get_bind(), checkfirst=True)
    notification_channel.drop(op.get_bind(), checkfirst=True)
