"""add teacher timetable and attendance link

Revision ID: c31b7a9f2d11
Revises: b2d8d7a1c4ef
Create Date: 2026-05-07 00:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "c31b7a9f2d11"
down_revision: Union[str, None] = "b2d8d7a1c4ef"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


timetable_day = postgresql.ENUM(
    "MONDAY",
    "TUESDAY",
    "WEDNESDAY",
    "THURSDAY",
    "FRIDAY",
    "SATURDAY",
    "SUNDAY",
    name="timetableday",
    create_type=False,
)


def upgrade() -> None:
    timetable_day.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "teacher_timetables",
        sa.Column("teacher_id", sa.UUID(), nullable=False),
        sa.Column("class_id", sa.UUID(), nullable=False),
        sa.Column("section_id", sa.UUID(), nullable=False),
        sa.Column("subject_id", sa.UUID(), nullable=False),
        sa.Column("academic_year_id", sa.UUID(), nullable=False),
        sa.Column("day_of_week", timetable_day, nullable=False),
        sa.Column("start_time", sa.Time(), nullable=False),
        sa.Column("end_time", sa.Time(), nullable=False),
        sa.Column("room_no", sa.String(length=50), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["academic_year_id"], ["academic_years.id"]),
        sa.ForeignKeyConstraint(["class_id"], ["classes.id"]),
        sa.ForeignKeyConstraint(["section_id"], ["sections.id"]),
        sa.ForeignKeyConstraint(["subject_id"], ["subjects.id"]),
        sa.ForeignKeyConstraint(["teacher_id"], ["teachers.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("section_id", "day_of_week", "start_time"),
        sa.UniqueConstraint("teacher_id", "day_of_week", "start_time", "section_id"),
    )
    op.create_index(op.f("ix_teacher_timetables_teacher_id"), "teacher_timetables", ["teacher_id"], unique=False)
    op.create_index(op.f("ix_teacher_timetables_class_id"), "teacher_timetables", ["class_id"], unique=False)
    op.create_index(op.f("ix_teacher_timetables_section_id"), "teacher_timetables", ["section_id"], unique=False)
    op.create_index(op.f("ix_teacher_timetables_subject_id"), "teacher_timetables", ["subject_id"], unique=False)
    op.create_index(op.f("ix_teacher_timetables_academic_year_id"), "teacher_timetables", ["academic_year_id"], unique=False)

    op.add_column("attendance_sessions", sa.Column("timetable_id", sa.UUID(), nullable=True))
    op.create_index(op.f("ix_attendance_sessions_timetable_id"), "attendance_sessions", ["timetable_id"], unique=False)
    op.create_foreign_key(
        "fk_attendance_sessions_timetable_id_teacher_timetables",
        "attendance_sessions",
        "teacher_timetables",
        ["timetable_id"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_attendance_sessions_timetable_id_teacher_timetables",
        "attendance_sessions",
        type_="foreignkey",
    )
    op.drop_index(op.f("ix_attendance_sessions_timetable_id"), table_name="attendance_sessions")
    op.drop_column("attendance_sessions", "timetable_id")

    op.drop_index(op.f("ix_teacher_timetables_academic_year_id"), table_name="teacher_timetables")
    op.drop_index(op.f("ix_teacher_timetables_subject_id"), table_name="teacher_timetables")
    op.drop_index(op.f("ix_teacher_timetables_section_id"), table_name="teacher_timetables")
    op.drop_index(op.f("ix_teacher_timetables_class_id"), table_name="teacher_timetables")
    op.drop_index(op.f("ix_teacher_timetables_teacher_id"), table_name="teacher_timetables")
    op.drop_table("teacher_timetables")
    timetable_day.drop(op.get_bind(), checkfirst=True)
