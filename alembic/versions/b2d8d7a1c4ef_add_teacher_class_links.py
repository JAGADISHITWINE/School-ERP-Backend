"""add teacher class links

Revision ID: b2d8d7a1c4ef
Revises: 86e1f53d8cb5
Create Date: 2026-05-07 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b2d8d7a1c4ef"
down_revision: Union[str, None] = "86e1f53d8cb5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "teacher_classes",
        sa.Column("teacher_id", sa.UUID(), nullable=False),
        sa.Column("class_id", sa.UUID(), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(["class_id"], ["classes.id"]),
        sa.ForeignKeyConstraint(["teacher_id"], ["teachers.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("teacher_id", "class_id"),
    )
    op.create_index(
        op.f("ix_teacher_classes_teacher_id"),
        "teacher_classes",
        ["teacher_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_teacher_classes_class_id"),
        "teacher_classes",
        ["class_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_teacher_classes_class_id"), table_name="teacher_classes")
    op.drop_index(op.f("ix_teacher_classes_teacher_id"), table_name="teacher_classes")
    op.drop_table("teacher_classes")
