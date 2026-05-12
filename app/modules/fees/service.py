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
from app.modules.logs.service import log_activity


async def create_fee_type(db: AsyncSession, data: FeeTypeCreate) -> FeeType:
    obj = FeeType(**data.model_dump())
    db.add(obj); await db.flush(); await db.refresh(obj)
    return obj


async def list_fee_types(db: AsyncSession, institution_id: str, offset: int, limit: int):
    q = select(FeeType).where(FeeType.institution_id == institution_id)
    total = (await db.execute(select(func.count()).select_from(q.subquery()))).scalar()
    result = await db.execute(q.offset(offset).limit(limit))
    return result.scalars().all(), total


async def create_fee_structure(db: AsyncSession, data: FeeStructureCreate, institution_id: str | None = None) -> FeeStructure:
    fee_type = (
        await db.execute(select(FeeType).where(FeeType.id == data.fee_type_id))
    ).scalar_one_or_none()
    if not fee_type:
        raise NotFoundError("Fee type not found")
    if institution_id and str(fee_type.institution_id) != str(institution_id):
        raise BusinessRuleError("Fee type does not belong to your institution")
    obj = FeeStructure(**data.model_dump())
    db.add(obj); await db.flush(); await db.refresh(obj)
    return obj


async def list_fee_structures(db: AsyncSession, fee_type_id: str, offset: int, limit: int):
    q = select(FeeStructure).where(FeeStructure.fee_type_id == fee_type_id)
    total = (await db.execute(select(func.count()).select_from(q.subquery()))).scalar()
    result = await db.execute(q.offset(offset).limit(limit))
    return result.scalars().all(), total


async def create_student_fee(db: AsyncSession, data: StudentFeeCreate, institution_id: str | None = None) -> StudentFee:
    row = (
        await db.execute(
            select(Student.id, FeeType.institution_id)
            .select_from(Student)
            .join(User, User.id == Student.user_id)
            .join(FeeStructure, FeeStructure.id == data.fee_structure_id)
            .join(FeeType, FeeType.id == FeeStructure.fee_type_id)
            .where(Student.id == data.student_id)
        )
    ).first()
    if not row:
        raise NotFoundError("Student or fee structure not found")
    if institution_id and str(row[1]) != str(institution_id):
        raise BusinessRuleError("Fee structure does not belong to your institution")
    obj = StudentFee(**data.model_dump())
    db.add(obj); await db.flush(); await db.refresh(obj)
    return obj


async def list_student_fees(db: AsyncSession, student_id: str, institution_id: str | None = None):
    q = (
        select(StudentFee)
        .join(Student, Student.id == StudentFee.student_id)
        .join(User, User.id == Student.user_id)
        .where(StudentFee.student_id == student_id)
    )
    if institution_id:
        q = q.where(User.institution_id == institution_id)
    result = await db.execute(q)
    return result.scalars().all()


async def list_all_student_fees(
    db: AsyncSession,
    offset: int,
    limit: int,
    student_id: str | None = None,
    institution_id: str | None = None,
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
    if institution_id:
        q = q.where(User.institution_id == institution_id, FeeType.institution_id == institution_id)
    if student_id:
        q = q.where(StudentFee.student_id == student_id)

    total = (await db.execute(select(func.count()).select_from(q.subquery()))).scalar()
    result = await db.execute(
        q.order_by(StudentFee.due_date.asc().nullslast(), StudentFee.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    return result.all(), total


async def collect_payment(
    db: AsyncSession,
    data: PaymentCreate,
    institution_id: str | None = None,
    actor_user_id: str | None = None,
) -> FeePayment:
    student_fee = (
        await db.execute(
            select(StudentFee)
            .join(Student, Student.id == StudentFee.student_id)
            .join(User, User.id == Student.user_id)
            .join(FeeStructure, FeeStructure.id == StudentFee.fee_structure_id)
            .join(FeeType, FeeType.id == FeeStructure.fee_type_id)
            .where(StudentFee.id == data.student_fee_id)
            .where(User.institution_id == institution_id if institution_id else True)
            .where(FeeType.institution_id == institution_id if institution_id else True)
        )
    ).scalar_one_or_none()
    if not student_fee:
        raise NotFoundError("Student fee record not found")

    if student_fee.status in (FeeStatus.PAID, FeeStatus.WAIVED):
        raise BusinessRuleError("Fee is already fully paid")
    if data.payment_mode != "cash" and not (data.transaction_ref or "").strip():
        raise BusinessRuleError("Transaction reference is required for non-cash payments")

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
    await log_activity(
        db,
        module="fees",
        action="payment_collect",
        actor_user_id=actor_user_id,
        institution_id=institution_id,
        entity_type="fee_payment",
        entity_id=str(payment.id),
        message="Fee payment collected",
        meta={
            "student_fee_id": str(student_fee.id),
            "amount": float(payment.amount),
            "payment_mode": payment.payment_mode,
            "transaction_ref": payment.transaction_ref,
            "status": student_fee.status,
        },
    )
    return payment


async def list_payments(db: AsyncSession, student_fee_id: str, institution_id: str | None = None):
    q = (
        select(FeePayment)
        .join(StudentFee, StudentFee.id == FeePayment.student_fee_id)
        .join(Student, Student.id == StudentFee.student_id)
        .join(User, User.id == Student.user_id)
        .where(FeePayment.student_fee_id == student_fee_id)
    )
    if institution_id:
        q = q.where(User.institution_id == institution_id)
    result = await db.execute(q.order_by(FeePayment.paid_at.desc()))
    return result.scalars().all()
