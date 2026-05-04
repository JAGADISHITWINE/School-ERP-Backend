import uuid
from datetime import date
from sqlalchemy import String, ForeignKey, Date, Integer, Numeric, Boolean, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from app.db.base import Base, TimestampMixin, UUIDPrimaryKey
import enum


class ExamWorkflow(str, enum.Enum):
    DRAFT = "draft"
    SUBMITTED = "submitted"
    LOCKED = "locked"


class Exam(UUIDPrimaryKey, TimestampMixin, Base):
    __tablename__ = "exams"

    institution_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("institutions.id"), nullable=False, index=True)
    academic_year_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("academic_years.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    exam_type: Mapped[str] = mapped_column(String(50), nullable=False)  # midterm, final, unit_test
    workflow_status: Mapped[ExamWorkflow] = mapped_column(
        SAEnum(ExamWorkflow), default=ExamWorkflow.DRAFT, nullable=False
    )

    exam_subjects: Mapped[list["ExamSubject"]] = relationship(back_populates="exam", cascade="all, delete-orphan")


class ExamSubject(UUIDPrimaryKey, Base):
    __tablename__ = "exam_subjects"

    exam_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("exams.id"), nullable=False, index=True)
    subject_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("subjects.id"), nullable=False)
    max_marks: Mapped[int] = mapped_column(Integer, nullable=False)
    pass_marks: Mapped[int] = mapped_column(Integer, nullable=False)
    exam_date: Mapped[date | None] = mapped_column(Date)

    exam: Mapped["Exam"] = relationship(back_populates="exam_subjects")
    subject: Mapped["Subject"] = relationship()
    marks: Mapped[list["Mark"]] = relationship(back_populates="exam_subject", cascade="all, delete-orphan")


class Mark(UUIDPrimaryKey, Base):
    __tablename__ = "marks"

    exam_subject_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("exam_subjects.id"), nullable=False, index=True)
    student_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("students.id"), nullable=False, index=True)
    marks_obtained: Mapped[float | None] = mapped_column(Numeric(6, 2))
    is_absent: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_locked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    exam_subject: Mapped["ExamSubject"] = relationship(back_populates="marks")
    student: Mapped["Student"] = relationship()
