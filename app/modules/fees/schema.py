import uuid
from pydantic import BaseModel, field_validator
from datetime import date, datetime
from app.modules.fees.model import FeeStatus


class FeeTypeCreate(BaseModel):
    institution_id: uuid.UUID
    name: str
    description: str | None = None


class FeeTypeOut(BaseModel):
    id: uuid.UUID
    institution_id: uuid.UUID
    name: str
    description: str | None

    class Config:
        from_attributes = True


class FeeStructureCreate(BaseModel):
    fee_type_id: uuid.UUID
    course_id: uuid.UUID
    academic_year_id: uuid.UUID
    amount: float
    frequency: str

    @field_validator("amount")
    @classmethod
    def positive_amount(cls, value):
        if value <= 0:
            raise ValueError("Amount must be greater than zero")
        return value

    @field_validator("frequency")
    @classmethod
    def valid_frequency(cls, value):
        allowed = {"annual", "semester", "monthly", "one_time"}
        normalized = value.strip().lower()
        if normalized not in allowed:
            raise ValueError("Frequency must be annual, semester, monthly, or one_time")
        return normalized


class FeeStructureOut(BaseModel):
    id: uuid.UUID
    fee_type_id: uuid.UUID
    course_id: uuid.UUID
    academic_year_id: uuid.UUID
    amount: float
    frequency: str

    class Config:
        from_attributes = True


class StudentFeeCreate(BaseModel):
    student_id: uuid.UUID
    fee_structure_id: uuid.UUID
    amount_due: float
    due_date: date | None = None

    @field_validator("amount_due")
    @classmethod
    def positive_due(cls, value):
        if value <= 0:
            raise ValueError("Amount due must be greater than zero")
        return value


class StudentFeeOut(BaseModel):
    id: uuid.UUID
    student_id: uuid.UUID
    fee_structure_id: uuid.UUID
    amount_due: float
    amount_paid: float
    status: FeeStatus
    due_date: date | None

    class Config:
        from_attributes = True


class StudentFeeListOut(StudentFeeOut):
    student_name: str | None = None
    roll_number: str | None = None
    fee_type_name: str | None = None
    course_name: str | None = None
    academic_year_label: str | None = None
    frequency: str | None = None


class PaymentCreate(BaseModel):
    student_fee_id: uuid.UUID
    amount: float
    payment_mode: str
    transaction_ref: str | None = None

    @field_validator("amount")
    @classmethod
    def positive_payment(cls, value):
        if value <= 0:
            raise ValueError("Payment amount must be greater than zero")
        return value

    @field_validator("payment_mode")
    @classmethod
    def valid_payment_mode(cls, value):
        allowed = {"cash", "upi", "card", "neft", "rtgs", "cheque", "online"}
        normalized = value.strip().lower()
        if normalized not in allowed:
            raise ValueError("Unsupported payment mode")
        return normalized


class PaymentOut(BaseModel):
    id: uuid.UUID
    student_fee_id: uuid.UUID
    amount: float
    payment_mode: str
    transaction_ref: str | None
    paid_at: datetime

    class Config:
        from_attributes = True
