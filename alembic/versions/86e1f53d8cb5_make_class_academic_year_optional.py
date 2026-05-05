"""make class academic year optional

Revision ID: 86e1f53d8cb5
Revises: 1d0d2d8d3f9b
Create Date: 2026-05-05 18:40:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "86e1f53d8cb5"
down_revision: Union[str, None] = "1d0d2d8d3f9b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column("classes", "academic_year_id", existing_type=sa.UUID(), nullable=True)


def downgrade() -> None:
    op.alter_column("classes", "academic_year_id", existing_type=sa.UUID(), nullable=False)
