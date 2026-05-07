"""universal academic structure

Revision ID: 4a7b9c2d1e33
Revises: 9f1d2c4e7b11
Create Date: 2026-05-07
"""

from alembic import op
import sqlalchemy as sa


revision = "4a7b9c2d1e33"
down_revision = "9f1d2c4e7b11"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("classes", sa.Column("course_id", sa.UUID(), nullable=True))
    op.add_column("classes", sa.Column("year_no", sa.Integer(), nullable=True))
    op.add_column("classes", sa.Column("intake_capacity", sa.Integer(), nullable=False, server_default="60"))
    op.alter_column("classes", "branch_id", existing_type=sa.UUID(), nullable=True)
    op.alter_column("classes", "semester", existing_type=sa.Integer(), nullable=True)
    op.create_index(op.f("ix_classes_course_id"), "classes", ["course_id"], unique=False)
    op.create_foreign_key("fk_classes_course_id", "classes", "courses", ["course_id"], ["id"])

    op.add_column("subjects", sa.Column("course_id", sa.UUID(), nullable=True))
    op.add_column("subjects", sa.Column("class_id", sa.UUID(), nullable=True))
    op.add_column("subjects", sa.Column("semester", sa.Integer(), nullable=True))
    op.alter_column("subjects", "branch_id", existing_type=sa.UUID(), nullable=True)
    op.create_index(op.f("ix_subjects_course_id"), "subjects", ["course_id"], unique=False)
    op.create_index(op.f("ix_subjects_class_id"), "subjects", ["class_id"], unique=False)
    op.create_foreign_key("fk_subjects_course_id", "subjects", "courses", ["course_id"], ["id"])
    op.create_foreign_key("fk_subjects_class_id", "subjects", "classes", ["class_id"], ["id"])

    op.execute(
        """
        UPDATE classes c
        SET course_id = b.course_id
        FROM branches b
        WHERE c.branch_id = b.id AND c.course_id IS NULL
        """
    )
    op.execute(
        """
        UPDATE subjects s
        SET course_id = b.course_id
        FROM branches b
        WHERE s.branch_id = b.id AND s.course_id IS NULL
        """
    )


def downgrade() -> None:
    op.drop_constraint("fk_subjects_class_id", "subjects", type_="foreignkey")
    op.drop_constraint("fk_subjects_course_id", "subjects", type_="foreignkey")
    op.drop_index(op.f("ix_subjects_class_id"), table_name="subjects")
    op.drop_index(op.f("ix_subjects_course_id"), table_name="subjects")
    op.alter_column("subjects", "branch_id", existing_type=sa.UUID(), nullable=False)
    op.drop_column("subjects", "semester")
    op.drop_column("subjects", "class_id")
    op.drop_column("subjects", "course_id")

    op.drop_constraint("fk_classes_course_id", "classes", type_="foreignkey")
    op.drop_index(op.f("ix_classes_course_id"), table_name="classes")
    op.alter_column("classes", "semester", existing_type=sa.Integer(), nullable=False)
    op.alter_column("classes", "branch_id", existing_type=sa.UUID(), nullable=False)
    op.drop_column("classes", "intake_capacity")
    op.drop_column("classes", "year_no")
    op.drop_column("classes", "course_id")
