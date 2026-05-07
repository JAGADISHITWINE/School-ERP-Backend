"""add hod and teacher hod subject links

Revision ID: d4f5a6b7c8d9
Revises: 4a7b9c2d1e33
Create Date: 2026-05-07 16:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d4f5a6b7c8d9"
down_revision: Union[str, None] = "4a7b9c2d1e33"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "hod_links",
        sa.Column("hod_teacher_id", sa.UUID(), nullable=False),
        sa.Column("institution_id", sa.UUID(), nullable=False),
        sa.Column("course_id", sa.UUID(), nullable=False),
        sa.Column("branch_id", sa.UUID(), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["branch_id"], ["branches.id"]),
        sa.ForeignKeyConstraint(["course_id"], ["courses.id"]),
        sa.ForeignKeyConstraint(["hod_teacher_id"], ["teachers.id"]),
        sa.ForeignKeyConstraint(["institution_id"], ["institutions.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("hod_teacher_id", "institution_id", "course_id", "branch_id"),
    )
    op.create_index(op.f("ix_hod_links_hod_teacher_id"), "hod_links", ["hod_teacher_id"], unique=False)
    op.create_index(op.f("ix_hod_links_institution_id"), "hod_links", ["institution_id"], unique=False)
    op.create_index(op.f("ix_hod_links_course_id"), "hod_links", ["course_id"], unique=False)
    op.create_index(op.f("ix_hod_links_branch_id"), "hod_links", ["branch_id"], unique=False)

    op.create_table(
        "teacher_hod_subject_links",
        sa.Column("teacher_id", sa.UUID(), nullable=False),
        sa.Column("hod_link_id", sa.UUID(), nullable=False),
        sa.Column("subject_id", sa.UUID(), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["hod_link_id"], ["hod_links.id"]),
        sa.ForeignKeyConstraint(["subject_id"], ["subjects.id"]),
        sa.ForeignKeyConstraint(["teacher_id"], ["teachers.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("teacher_id", "hod_link_id", "subject_id"),
    )
    op.create_index(op.f("ix_teacher_hod_subject_links_teacher_id"), "teacher_hod_subject_links", ["teacher_id"], unique=False)
    op.create_index(op.f("ix_teacher_hod_subject_links_hod_link_id"), "teacher_hod_subject_links", ["hod_link_id"], unique=False)
    op.create_index(op.f("ix_teacher_hod_subject_links_subject_id"), "teacher_hod_subject_links", ["subject_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_teacher_hod_subject_links_subject_id"), table_name="teacher_hod_subject_links")
    op.drop_index(op.f("ix_teacher_hod_subject_links_hod_link_id"), table_name="teacher_hod_subject_links")
    op.drop_index(op.f("ix_teacher_hod_subject_links_teacher_id"), table_name="teacher_hod_subject_links")
    op.drop_table("teacher_hod_subject_links")

    op.drop_index(op.f("ix_hod_links_branch_id"), table_name="hod_links")
    op.drop_index(op.f("ix_hod_links_course_id"), table_name="hod_links")
    op.drop_index(op.f("ix_hod_links_institution_id"), table_name="hod_links")
    op.drop_index(op.f("ix_hod_links_hod_teacher_id"), table_name="hod_links")
    op.drop_table("hod_links")
