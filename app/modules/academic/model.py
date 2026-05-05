import uuid
from datetime import date
from sqlalchemy import String, Boolean, ForeignKey, Integer, Date
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from app.db.base import Base, TimestampMixin, UUIDPrimaryKey


class AcademicYear(UUIDPrimaryKey, TimestampMixin, Base):
    __tablename__ = "academic_years"

    institution_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("institutions.id"), nullable=False, index=True
    )
    label: Mapped[str] = mapped_column(String(50), nullable=False)  # e.g. "2024-25"
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    is_current: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class Course(UUIDPrimaryKey, TimestampMixin, Base):
    __tablename__ = "courses"

    institution_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("institutions.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    level: Mapped[str] = mapped_column(String(50), nullable=False)  # UG, PG, Diploma
    duration_years: Mapped[int] = mapped_column(Integer, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    branches: Mapped[list["Branch"]] = relationship(back_populates="course")


class Branch(UUIDPrimaryKey, TimestampMixin, Base):
    __tablename__ = "branches"

    course_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("courses.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    code: Mapped[str] = mapped_column(String(20), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    course: Mapped["Course"] = relationship(back_populates="branches")
    subjects: Mapped[list["Subject"]] = relationship(back_populates="branch")
    classes: Mapped[list["Class"]] = relationship(back_populates="branch")


class Subject(UUIDPrimaryKey, TimestampMixin, Base):
    __tablename__ = "subjects"

    branch_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("branches.id"), nullable=False, index=True
    )
    academic_year_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("academic_years.id"), nullable=True, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    code: Mapped[str] = mapped_column(String(20), nullable=False)
    credits: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    branch: Mapped["Branch"] = relationship(back_populates="subjects")


class Class(UUIDPrimaryKey, TimestampMixin, Base):
    __tablename__ = "classes"

    branch_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("branches.id"), nullable=False, index=True
    )
    academic_year_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("academic_years.id"), nullable=True, index=True
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)  # e.g. "Second Year"
    semester: Mapped[int] = mapped_column(Integer, nullable=False)

    branch: Mapped["Branch"] = relationship(back_populates="classes")
    sections: Mapped[list["Section"]] = relationship(back_populates="class_")


class Section(UUIDPrimaryKey, TimestampMixin, Base):
    __tablename__ = "sections"

    class_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("classes.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(10), nullable=False)  # A, B, C
    max_strength: Mapped[int] = mapped_column(Integer, default=60, nullable=False)

    class_: Mapped["Class"] = relationship(back_populates="sections")
