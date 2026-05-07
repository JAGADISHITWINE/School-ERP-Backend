import uuid
from datetime import date, time
import enum
from sqlalchemy import String, ForeignKey, Date, Time, Enum as SAEnum, UniqueConstraint, Integer, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from app.db.base import Base, TimestampMixin, UUIDPrimaryKey


class TimetableDay(str, enum.Enum):
    MONDAY = "monday"
    TUESDAY = "tuesday"
    WEDNESDAY = "wednesday"
    THURSDAY = "thursday"
    FRIDAY = "friday"
    SATURDAY = "saturday"
    SUNDAY = "sunday"


class Teacher(UUIDPrimaryKey, TimestampMixin, Base):
    __tablename__ = "teachers"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), unique=True, nullable=False
    )
    employee_code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    designation: Mapped[str | None] = mapped_column(String(100))
    joined_at: Mapped[date | None] = mapped_column(Date)

    user: Mapped["User"] = relationship()
    teacher_subjects: Mapped[list["TeacherSubject"]] = relationship(back_populates="teacher")
    teacher_classes: Mapped[list["TeacherClass"]] = relationship(
        back_populates="teacher", cascade="all, delete-orphan"
    )
    timetable_entries: Mapped[list["TeacherTimetable"]] = relationship(
        back_populates="teacher", cascade="all, delete-orphan"
    )


class TeacherSubject(UUIDPrimaryKey, Base):
    __tablename__ = "teacher_subjects"
    __table_args__ = (UniqueConstraint("teacher_id", "subject_id", "section_id", "academic_year_id"),)

    teacher_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("teachers.id"), nullable=False, index=True)
    subject_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("subjects.id"), nullable=False)
    section_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("sections.id"), nullable=False)
    academic_year_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("academic_years.id"), nullable=False)

    teacher: Mapped["Teacher"] = relationship(back_populates="teacher_subjects")
    subject: Mapped["Subject"] = relationship()
    section: Mapped["Section"] = relationship()


class TeacherClass(UUIDPrimaryKey, Base):
    __tablename__ = "teacher_classes"
    __table_args__ = (UniqueConstraint("teacher_id", "class_id"),)

    teacher_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("teachers.id"), nullable=False, index=True
    )
    class_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("classes.id"), nullable=False, index=True
    )

    teacher: Mapped["Teacher"] = relationship(back_populates="teacher_classes")
    class_: Mapped["Class"] = relationship()


class TeacherTimetable(UUIDPrimaryKey, TimestampMixin, Base):
    __tablename__ = "teacher_timetables"
    __table_args__ = (
        UniqueConstraint("teacher_id", "day_of_week", "start_time", "section_id"),
        UniqueConstraint("section_id", "day_of_week", "start_time"),
    )

    teacher_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("teachers.id"), nullable=False, index=True
    )
    class_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("classes.id"), nullable=False, index=True
    )
    section_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sections.id"), nullable=False, index=True
    )
    subject_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("subjects.id"), nullable=False, index=True
    )
    academic_year_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("academic_years.id"), nullable=False, index=True
    )
    day_of_week: Mapped[TimetableDay] = mapped_column(SAEnum(TimetableDay), nullable=False)
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)
    room_no: Mapped[str | None] = mapped_column(String(50))
    version_no: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    teacher: Mapped["Teacher"] = relationship(back_populates="timetable_entries")
    class_: Mapped["Class"] = relationship()
    section: Mapped["Section"] = relationship()
    subject: Mapped["Subject"] = relationship()
