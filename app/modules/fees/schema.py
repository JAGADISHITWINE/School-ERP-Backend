import uuid
from pydantic import BaseModel
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


class PaymentCreate(BaseModel):
    student_fee_id: uuid.UUID
    amount: float
    payment_mode: str
    transaction_ref: str | None = None


class PaymentOut(BaseModel):
    id: uuid.UUID
    student_fee_id: uuid.UUID
    amount: float
    payment_mode: str
    transaction_ref: str | None
    paid_at: datetime

    class Config:
        from_attributes = True
