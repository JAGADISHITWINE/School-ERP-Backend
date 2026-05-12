"""add section to teacher subject links

Revision ID: b8d1f4a6c902
Revises: a7c9d2e5f601
Create Date: 2026-05-12 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "b8d1f4a6c902"
down_revision: Union[str, None] = "a7c9d2e5f601"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "teacher_hod_subject_links",
        sa.Column("section_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_teacher_hod_subject_links_section_id_sections",
        "teacher_hod_subject_links",
        "sections",
        ["section_id"],
        ["id"],
    )
    op.create_index(
        op.f("ix_teacher_hod_subject_links_section_id"),
        "teacher_hod_subject_links",
        ["section_id"],
        unique=False,
    )
    op.drop_constraint(
        "teacher_hod_subject_links_teacher_id_hod_link_id_subject_id_key",
        "teacher_hod_subject_links",
        type_="unique",
    )
    op.create_unique_constraint(
        "uq_teacher_hod_subject_section",
        "teacher_hod_subject_links",
        ["teacher_id", "hod_link_id", "section_id", "subject_id"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_teacher_hod_subject_section", "teacher_hod_subject_links", type_="unique")
    op.create_unique_constraint(
        "teacher_hod_subject_links_teacher_id_hod_link_id_subject_id_key",
        "teacher_hod_subject_links",
        ["teacher_id", "hod_link_id", "subject_id"],
    )
    op.drop_index(op.f("ix_teacher_hod_subject_links_section_id"), table_name="teacher_hod_subject_links")
    op.drop_constraint(
        "fk_teacher_hod_subject_links_section_id_sections",
        "teacher_hod_subject_links",
        type_="foreignkey",
    )
    op.drop_column("teacher_hod_subject_links", "section_id")
