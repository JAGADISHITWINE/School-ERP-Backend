from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.modules.academic.model import AcademicYear, Course
from app.modules.fees.model import FeeType, FeeStructure, StudentFee, FeePayment, FeeStatus
from app.modules.fees.schema import (
    FeeTypeCreate, FeeStructureCreate, StudentFeeCreate, PaymentCreate
)
from app.modules.students.model import Student
from app.modules.users.model import User
from app.core.exceptions import NotFoundError, BusinessRuleError


async def create_fee_type(db: AsyncSession, data: FeeTypeCreate) -> FeeType:
    obj = FeeType(**data.model_dump())
    db.add(obj); await db.flush(); await db.refresh(obj)
    return obj


async def list_fee_types(db: AsyncSession, institution_id: str, offset: int, limit: int):
    q = select(FeeType).where(FeeType.institution_id == institution_id)
    total = (await db.execute(select(func.count()).select_from(q.subquery()))).scalar()
    result = await db.execute(q.offset(offset).limit(limit))
    return result.scalars().all(), total


async def create_fee_structure(db: AsyncSession, data: FeeStructureCreate) -> FeeStructure:
    obj = FeeStructure(**data.model_dump())
    db.add(obj); await db.flush(); await db.refresh(obj)
    return obj


async def list_fee_structures(db: AsyncSession, fee_type_id: str, offset: int, limit: int):
    q = select(FeeStructure).where(FeeStructure.fee_type_id == fee_type_id)
    total = (await db.execute(select(func.count()).select_from(q.subquery()))).scalar()
    result = await db.execute(q.offset(offset).limit(limit))
    return result.scalars().all(), total


async def create_student_fee(db: AsyncSession, data: StudentFeeCreate) -> StudentFee:
    obj = StudentFee(**data.model_dump())
    db.add(obj); await db.flush(); await db.refresh(obj)
    return obj


async def list_student_fees(db: AsyncSession, student_id: str):
    result = await db.execute(
        select(StudentFee).where(StudentFee.student_id == student_id)
    )
    return result.scalars().all()


async def list_all_student_fees(
    db: AsyncSession,
    offset: int,
    limit: int,
    student_id: str | None = None,
):
    q = (
        select(
            StudentFee,
            User.full_name.label("student_name"),
            Student.roll_number.label("roll_number"),
            FeeType.name.label("fee_type_name"),
            Course.name.label("course_name"),
            AcademicYear.label.label("academic_year_label"),
            FeeStructure.frequency.label("frequency"),
        )
        .join(Student, Student.id == StudentFee.student_id)
        .join(User, User.id == Student.user_id)
        .join(FeeStructure, FeeStructure.id == StudentFee.fee_structure_id)
        .join(FeeType, FeeType.id == FeeStructure.fee_type_id)
        .join(Course, Course.id == FeeStructure.course_id)
        .join(AcademicYear, AcademicYear.id == FeeStructure.academic_year_id)
    )
    if student_id:
        q = q.where(StudentFee.student_id == student_id)

    total = (await db.execute(select(func.count()).select_from(q.subquery()))).scalar()
    result = await db.execute(
        q.order_by(StudentFee.due_date.asc().nullslast(), StudentFee.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    return result.all(), total


async def collect_payment(db: AsyncSession, data: PaymentCreate) -> FeePayment:
    student_fee = (
        await db.execute(select(StudentFee).where(StudentFee.id == data.student_fee_id))
    ).scalar_one_or_none()
    if not student_fee:
        raise NotFoundError("Student fee record not found")

    if student_fee.status == FeeStatus.PAID:
        raise BusinessRuleError("Fee is already fully paid")

    remaining = float(student_fee.amount_due) - float(student_fee.amount_paid)
    if data.amount > remaining:
        raise BusinessRuleError(
            f"Payment amount {data.amount} exceeds remaining balance {remaining:.2f}"
        )

    payment = FeePayment(
        student_fee_id=str(data.student_fee_id),
        amount=data.amount,
        payment_mode=data.payment_mode,
        transaction_ref=data.transaction_ref,
    )
    db.add(payment)

    student_fee.amount_paid = float(student_fee.amount_paid) + data.amount
    if float(student_fee.amount_paid) >= float(student_fee.amount_due):
        student_fee.status = FeeStatus.PAID
    else:
        student_fee.status = FeeStatus.PARTIAL

    await db.flush()
    await db.refresh(payment)
    return payment


async def list_payments(db: AsyncSession, student_fee_id: str):
    result = await db.execute(
        select(FeePayment).where(FeePayment.student_fee_id == student_fee_id)
        .order_by(FeePayment.paid_at.desc())
    )
    return result.scalars().all()
