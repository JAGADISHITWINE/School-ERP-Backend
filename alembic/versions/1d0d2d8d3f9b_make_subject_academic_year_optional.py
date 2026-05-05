"""make subject academic year optional

Revision ID: 1d0d2d8d3f9b
Revises: 8344c5860842
Create Date: 2026-05-05 18:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "1d0d2d8d3f9b"
down_revision: Union[str, None] = "8344c5860842"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column("subjects", "academic_year_id", existing_type=sa.UUID(), nullable=True)


def downgrade() -> None:
    op.alter_column("subjects", "academic_year_id", existing_type=sa.UUID(), nullable=False)
