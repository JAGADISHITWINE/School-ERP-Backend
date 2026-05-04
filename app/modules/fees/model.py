import uuid
from datetime import date, datetime, timezone
from sqlalchemy import String, ForeignKey, Date, Numeric, DateTime, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from app.db.base import Base, TimestampMixin, UUIDPrimaryKey
import enum


class FeeStatus(str, enum.Enum):
    UNPAID = "unpaid"
    PARTIAL = "partial"
    PAID = "paid"
    WAIVED = "waived"


class FeeType(UUIDPrimaryKey, TimestampMixin, Base):
    __tablename__ = "fee_types"

    institution_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("institutions.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(String(300))

    structures: Mapped[list["FeeStructure"]] = relationship(back_populates="fee_type")


class FeeStructure(UUIDPrimaryKey, TimestampMixin, Base):
    __tablename__ = "fee_structures"

    fee_type_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("fee_types.id"), nullable=False, index=True)
    course_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("courses.id"), nullable=False)
    academic_year_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("academic_years.id"), nullable=False)
    amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    frequency: Mapped[str] = mapped_column(String(20), nullable=False)  # annual, semester, monthly

    fee_type: Mapped["FeeType"] = relationship(back_populates="structures")
    student_fees: Mapped[list["StudentFee"]] = relationship(back_populates="fee_structure")


class StudentFee(UUIDPrimaryKey, TimestampMixin, Base):
    __tablename__ = "student_fees"

    student_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("students.id"), nullable=False, index=True)
    fee_structure_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("fee_structures.id"), nullable=False)
    amount_due: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    amount_paid: Mapped[float] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    status: Mapped[FeeStatus] = mapped_column(SAEnum(FeeStatus), default=FeeStatus.UNPAID, nullable=False)
    due_date: Mapped[date | None] = mapped_column(Date)

    fee_structure: Mapped["FeeStructure"] = relationship(back_populates="student_fees")
    payments: Mapped[list["FeePayment"]] = relationship(back_populates="student_fee", cascade="all, delete-orphan")


class FeePayment(UUIDPrimaryKey, Base):
    __tablename__ = "fee_payments"

    student_fee_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("student_fees.id"), nullable=False, index=True)
    amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    payment_mode: Mapped[str] = mapped_column(String(30), nullable=False)  # cash, upi, card, neft
    transaction_ref: Mapped[str | None] = mapped_column(String(100))
    paid_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    student_fee: Mapped["StudentFee"] = relationship(back_populates="payments")
