"""add class mentor management

Revision ID: a7c9d2e5f601
Revises: f6a7b8c9d0e1
Create Date: 2026-05-12 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "a7c9d2e5f601"
down_revision: Union[str, None] = "f6a7b8c9d0e1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "class_mentors",
        sa.Column("teacher_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("academic_year_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("class_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("section_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("assigned_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["academic_year_id"], ["academic_years.id"]),
        sa.ForeignKeyConstraint(["assigned_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["class_id"], ["classes.id"]),
        sa.ForeignKeyConstraint(["section_id"], ["sections.id"]),
        sa.ForeignKeyConstraint(["teacher_id"], ["teachers.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("academic_year_id", "class_id", "section_id", name="uq_class_mentor_scope"),
        sa.UniqueConstraint("teacher_id", "academic_year_id", "class_id", "section_id", name="uq_teacher_class_mentor_scope"),
    )
    op.create_index(op.f("ix_class_mentors_academic_year_id"), "class_mentors", ["academic_year_id"], unique=False)
    op.create_index(op.f("ix_class_mentors_assigned_by_user_id"), "class_mentors", ["assigned_by_user_id"], unique=False)
    op.create_index(op.f("ix_class_mentors_class_id"), "class_mentors", ["class_id"], unique=False)
    op.create_index(op.f("ix_class_mentors_section_id"), "class_mentors", ["section_id"], unique=False)
    op.create_index(op.f("ix_class_mentors_teacher_id"), "class_mentors", ["teacher_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_class_mentors_teacher_id"), table_name="class_mentors")
    op.drop_index(op.f("ix_class_mentors_section_id"), table_name="class_mentors")
    op.drop_index(op.f("ix_class_mentors_class_id"), table_name="class_mentors")
    op.drop_index(op.f("ix_class_mentors_assigned_by_user_id"), table_name="class_mentors")
    op.drop_index(op.f("ix_class_mentors_academic_year_id"), table_name="class_mentors")
    op.drop_table("class_mentors")
