"""add teacher content modules

Revision ID: f6a7b8c9d0e1
Revises: 8d3a6e4b9c10
Create Date: 2026-05-12 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "f6a7b8c9d0e1"
down_revision: Union[str, None] = "8d3a6e4b9c10"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


material_type = postgresql.ENUM("PDF", "DOC", "PPT", "IMAGE", "VIDEO_LINK", "OTHER", name="materialtype", create_type=False)
assessment_type = postgresql.ENUM("QUIZ", "INTERNAL_TEST", "UNIT_TEST", "PRACTICAL", "OTHER", name="assessmenttype", create_type=False)


def upgrade() -> None:
    material_type.create(op.get_bind(), checkfirst=True)
    assessment_type.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "study_materials",
        sa.Column("teacher_id", sa.UUID(), nullable=False),
        sa.Column("academic_year_id", sa.UUID(), nullable=False),
        sa.Column("branch_id", sa.UUID(), nullable=False),
        sa.Column("class_id", sa.UUID(), nullable=False),
        sa.Column("section_id", sa.UUID(), nullable=False),
        sa.Column("subject_id", sa.UUID(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("material_type", material_type, nullable=False),
        sa.Column("file_name", sa.String(length=255), nullable=True),
        sa.Column("file_url", sa.String(length=500), nullable=True),
        sa.Column("external_url", sa.String(length=1000), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["academic_year_id"], ["academic_years.id"]),
        sa.ForeignKeyConstraint(["branch_id"], ["branches.id"]),
        sa.ForeignKeyConstraint(["class_id"], ["classes.id"]),
        sa.ForeignKeyConstraint(["section_id"], ["sections.id"]),
        sa.ForeignKeyConstraint(["subject_id"], ["subjects.id"]),
        sa.ForeignKeyConstraint(["teacher_id"], ["teachers.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    for col in ("teacher_id", "academic_year_id", "branch_id", "class_id", "section_id", "subject_id"):
        op.create_index(op.f(f"ix_study_materials_{col}"), "study_materials", [col], unique=False)

    op.create_table(
        "assessments",
        sa.Column("teacher_id", sa.UUID(), nullable=False),
        sa.Column("academic_year_id", sa.UUID(), nullable=False),
        sa.Column("branch_id", sa.UUID(), nullable=False),
        sa.Column("class_id", sa.UUID(), nullable=False),
        sa.Column("section_id", sa.UUID(), nullable=False),
        sa.Column("subject_id", sa.UUID(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("assessment_type", assessment_type, nullable=False),
        sa.Column("total_marks", sa.Integer(), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=False),
        sa.Column("instructions", sa.Text(), nullable=True),
        sa.Column("attachment_name", sa.String(length=255), nullable=True),
        sa.Column("attachment_url", sa.String(length=500), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["academic_year_id"], ["academic_years.id"]),
        sa.ForeignKeyConstraint(["branch_id"], ["branches.id"]),
        sa.ForeignKeyConstraint(["class_id"], ["classes.id"]),
        sa.ForeignKeyConstraint(["section_id"], ["sections.id"]),
        sa.ForeignKeyConstraint(["subject_id"], ["subjects.id"]),
        sa.ForeignKeyConstraint(["teacher_id"], ["teachers.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("title", "subject_id", "class_id", "section_id", "due_date", name="uq_assessment_title_scope_due"),
    )
    for col in ("teacher_id", "academic_year_id", "branch_id", "class_id", "section_id", "subject_id", "due_date"):
        op.create_index(op.f(f"ix_assessments_{col}"), "assessments", [col], unique=False)

    op.create_table(
        "assignments",
        sa.Column("teacher_id", sa.UUID(), nullable=False),
        sa.Column("academic_year_id", sa.UUID(), nullable=False),
        sa.Column("branch_id", sa.UUID(), nullable=False),
        sa.Column("class_id", sa.UUID(), nullable=False),
        sa.Column("section_id", sa.UUID(), nullable=False),
        sa.Column("subject_id", sa.UUID(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("total_marks", sa.Integer(), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=False),
        sa.Column("instructions", sa.Text(), nullable=True),
        sa.Column("attachment_name", sa.String(length=255), nullable=True),
        sa.Column("attachment_url", sa.String(length=500), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["academic_year_id"], ["academic_years.id"]),
        sa.ForeignKeyConstraint(["branch_id"], ["branches.id"]),
        sa.ForeignKeyConstraint(["class_id"], ["classes.id"]),
        sa.ForeignKeyConstraint(["section_id"], ["sections.id"]),
        sa.ForeignKeyConstraint(["subject_id"], ["subjects.id"]),
        sa.ForeignKeyConstraint(["teacher_id"], ["teachers.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    for col in ("teacher_id", "academic_year_id", "branch_id", "class_id", "section_id", "subject_id", "due_date"):
        op.create_index(op.f(f"ix_assignments_{col}"), "assignments", [col], unique=False)

    op.create_table(
        "assignment_submissions",
        sa.Column("assignment_id", sa.UUID(), nullable=False),
        sa.Column("student_id", sa.UUID(), nullable=False),
        sa.Column("remarks", sa.Text(), nullable=True),
        sa.Column("attachment_name", sa.String(length=255), nullable=True),
        sa.Column("attachment_url", sa.String(length=500), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["assignment_id"], ["assignments.id"]),
        sa.ForeignKeyConstraint(["student_id"], ["students.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("assignment_id", "student_id", name="uq_assignment_student_submission"),
    )
    op.create_index(op.f("ix_assignment_submissions_assignment_id"), "assignment_submissions", ["assignment_id"], unique=False)
    op.create_index(op.f("ix_assignment_submissions_student_id"), "assignment_submissions", ["student_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_assignment_submissions_student_id"), table_name="assignment_submissions")
    op.drop_index(op.f("ix_assignment_submissions_assignment_id"), table_name="assignment_submissions")
    op.drop_table("assignment_submissions")

    for col in ("due_date", "subject_id", "section_id", "class_id", "branch_id", "academic_year_id", "teacher_id"):
        op.drop_index(op.f(f"ix_assignments_{col}"), table_name="assignments")
    op.drop_table("assignments")

    for col in ("due_date", "subject_id", "section_id", "class_id", "branch_id", "academic_year_id", "teacher_id"):
        op.drop_index(op.f(f"ix_assessments_{col}"), table_name="assessments")
    op.drop_table("assessments")

    for col in ("subject_id", "section_id", "class_id", "branch_id", "academic_year_id", "teacher_id"):
        op.drop_index(op.f(f"ix_study_materials_{col}"), table_name="study_materials")
    op.drop_table("study_materials")

    assessment_type.drop(op.get_bind(), checkfirst=True)
    material_type.drop(op.get_bind(), checkfirst=True)
