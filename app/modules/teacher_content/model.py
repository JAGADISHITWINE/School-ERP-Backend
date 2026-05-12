import enum
import uuid
from datetime import date, datetime, timezone

from sqlalchemy import Date, DateTime, Enum as SAEnum, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKey


class MaterialType(str, enum.Enum):
    PDF = "pdf"
    DOC = "doc"
    PPT = "ppt"
    IMAGE = "image"
    VIDEO_LINK = "video_link"
    OTHER = "other"


class AssessmentType(str, enum.Enum):
    QUIZ = "quiz"
    INTERNAL_TEST = "internal_test"
    UNIT_TEST = "unit_test"
    PRACTICAL = "practical"
    OTHER = "other"


class StudyMaterial(UUIDPrimaryKey, TimestampMixin, Base):
    __tablename__ = "study_materials"

    teacher_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("teachers.id"), nullable=False, index=True)
    academic_year_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("academic_years.id"), nullable=False, index=True)
    branch_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("branches.id"), nullable=False, index=True)
    class_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("classes.id"), nullable=False, index=True)
    section_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("sections.id"), nullable=False, index=True)
    subject_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("subjects.id"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    material_type: Mapped[MaterialType] = mapped_column(SAEnum(MaterialType), nullable=False)
    file_name: Mapped[str | None] = mapped_column(String(255))
    file_url: Mapped[str | None] = mapped_column(String(500))
    external_url: Mapped[str | None] = mapped_column(String(1000))

    teacher: Mapped["Teacher"] = relationship()


class Assessment(UUIDPrimaryKey, TimestampMixin, Base):
    __tablename__ = "assessments"
    __table_args__ = (
        UniqueConstraint("title", "subject_id", "class_id", "section_id", "due_date", name="uq_assessment_title_scope_due"),
    )

    teacher_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("teachers.id"), nullable=False, index=True)
    academic_year_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("academic_years.id"), nullable=False, index=True)
    branch_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("branches.id"), nullable=False, index=True)
    class_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("classes.id"), nullable=False, index=True)
    section_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("sections.id"), nullable=False, index=True)
    subject_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("subjects.id"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    assessment_type: Mapped[AssessmentType] = mapped_column(SAEnum(AssessmentType), nullable=False)
    total_marks: Mapped[int] = mapped_column(Integer, nullable=False)
    due_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    instructions: Mapped[str | None] = mapped_column(Text)
    attachment_name: Mapped[str | None] = mapped_column(String(255))
    attachment_url: Mapped[str | None] = mapped_column(String(500))

    teacher: Mapped["Teacher"] = relationship()


class Assignment(UUIDPrimaryKey, TimestampMixin, Base):
    __tablename__ = "assignments"

    teacher_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("teachers.id"), nullable=False, index=True)
    academic_year_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("academic_years.id"), nullable=False, index=True)
    branch_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("branches.id"), nullable=False, index=True)
    class_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("classes.id"), nullable=False, index=True)
    section_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("sections.id"), nullable=False, index=True)
    subject_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("subjects.id"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    total_marks: Mapped[int] = mapped_column(Integer, nullable=False)
    due_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    instructions: Mapped[str | None] = mapped_column(Text)
    attachment_name: Mapped[str | None] = mapped_column(String(255))
    attachment_url: Mapped[str | None] = mapped_column(String(500))

    teacher: Mapped["Teacher"] = relationship()
    submissions: Mapped[list["AssignmentSubmission"]] = relationship(back_populates="assignment")


class AssignmentSubmission(UUIDPrimaryKey, TimestampMixin, Base):
    __tablename__ = "assignment_submissions"
    __table_args__ = (UniqueConstraint("assignment_id", "student_id", name="uq_assignment_student_submission"),)

    assignment_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("assignments.id"), nullable=False, index=True)
    student_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("students.id"), nullable=False, index=True)
    remarks: Mapped[str | None] = mapped_column(Text)
    attachment_name: Mapped[str | None] = mapped_column(String(255))
    attachment_url: Mapped[str | None] = mapped_column(String(500))
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    assignment: Mapped["Assignment"] = relationship(back_populates="submissions")
    student: Mapped["Student"] = relationship()
