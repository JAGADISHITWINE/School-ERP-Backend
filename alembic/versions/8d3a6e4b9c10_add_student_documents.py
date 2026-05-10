"""add student documents

Revision ID: 8d3a6e4b9c10
Revises: 7c2e9d8f1a33
Create Date: 2026-05-10 15:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "8d3a6e4b9c10"
down_revision: Union[str, None] = "7c2e9d8f1a33"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "student_documents",
        sa.Column("student_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_type", sa.String(length=80), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("file_name", sa.String(length=255), nullable=True),
        sa.Column("file_url", sa.String(length=500), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("remarks", sa.String(length=500), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["student_id"], ["students.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_student_documents_document_type"), "student_documents", ["document_type"], unique=False)
    op.create_index(op.f("ix_student_documents_status"), "student_documents", ["status"], unique=False)
    op.create_index(op.f("ix_student_documents_student_id"), "student_documents", ["student_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_student_documents_student_id"), table_name="student_documents")
    op.drop_index(op.f("ix_student_documents_status"), table_name="student_documents")
    op.drop_index(op.f("ix_student_documents_document_type"), table_name="student_documents")
    op.drop_table("student_documents")
