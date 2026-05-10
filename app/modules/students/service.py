from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.modules.students.model import Student, StudentAcademicRecord, StudentStatus, StudentDocument
from app.modules.users.model import User
from app.modules.roles.model import Role, UserRole
from app.modules.students.schema import StudentCreate, StudentUpdate, AcademicRecordCreate, StudentDocumentCreate, StudentDocumentUpdate
from app.core.security import hash_password
from app.core.exceptions import NotFoundError, ConflictError, BusinessRuleError


async def _get_student_role(db: AsyncSession, institution_id) -> Role | None:
    return (
        await db.execute(
            select(Role).where(
                Role.institution_id == institution_id,
                Role.slug == "student",
            )
        )
    ).scalar_one_or_none()


async def create_student(db: AsyncSession, data: StudentCreate) -> Student:
    # Check uniqueness
    ex_user = (await db.execute(select(User).where(User.email == data.email))).scalar_one_or_none()
    if ex_user:
        raise ConflictError("Email already registered")

    ex_roll = (await db.execute(select(Student).where(Student.roll_number == data.roll_number))).scalar_one_or_none()
    if ex_roll:
        raise ConflictError("Roll number already exists")

    # Create user account
    user = User(
        institution_id=data.institution_id,
        email=data.email,
        username=data.username,
        password_hash=hash_password(data.password),
        full_name=data.full_name,
        phone=data.phone,
    )
    db.add(user)
    await db.flush()

    student_role = await _get_student_role(db, data.institution_id)
    if student_role:
        db.add(UserRole(user_id=user.id, role_id=student_role.id))
        await db.flush()

    # Create student profile
    student = Student(
        user_id=user.id,
        roll_number=data.roll_number,
        date_of_birth=data.date_of_birth,
        gender=data.gender,
        guardian_name=data.guardian_name,
        guardian_phone=data.guardian_phone,
        guardian_email=data.guardian_email,
    )
    db.add(student)
    await db.flush()

    # Create initial academic record
    record = StudentAcademicRecord(
        student_id=student.id,
        section_id=data.section_id,
        branch_id=data.branch_id,
        academic_year_id=data.academic_year_id,
        status=StudentStatus.ACTIVE,
    )
    db.add(record)
    await db.flush()
    await db.refresh(student)
    return student


async def list_students(db: AsyncSession, institution_id: str, offset: int, limit: int):
    """List students belonging to an institution (via user FK)."""
    q = (
        select(Student)
        .join(User, Student.user_id == User.id)
        .where(User.institution_id == institution_id)
    )
    total = (await db.execute(select(func.count()).select_from(q.subquery()))).scalar()
    result = await db.execute(q.offset(offset).limit(limit))
    return result.scalars().all(), total


async def get_student(db: AsyncSession, student_id: str) -> Student:
    result = await db.execute(
        select(Student).where(Student.id == student_id)
    )
    student = result.scalar_one_or_none()
    if not student:
        raise NotFoundError("Student not found")
    return student


async def update_student(db: AsyncSession, student_id: str, data: StudentUpdate) -> Student:
    student = await get_student(db, student_id)
    # Update student profile fields
    for k, v in data.model_dump(exclude_none=True).items():
        if hasattr(student, k):
            setattr(student, k, v)
    # Also update the user's full_name/phone if passed
    user_data = {}
    if data.full_name:
        user_data["full_name"] = data.full_name
    if data.phone:
        user_data["phone"] = data.phone
    if user_data:
        user = (await db.execute(select(User).where(User.id == student.user_id))).scalar_one()
        for k, v in user_data.items():
            setattr(user, k, v)
    await db.flush()
    return student


async def create_academic_record(
    db: AsyncSession, student_id: str, data: AcademicRecordCreate
) -> StudentAcademicRecord:
    """Close the current active record and open a new one (branch change / new year)."""
    student = await get_student(db, student_id)

    # Close current active record
    active = (
        await db.execute(
            select(StudentAcademicRecord).where(
                StudentAcademicRecord.student_id == student_id,
                StudentAcademicRecord.exited_at == None,
            )
        )
    ).scalar_one_or_none()

    if active:
        active.exited_at = datetime.now(timezone.utc)
        active.status = StudentStatus.TRANSFERRED

    record = StudentAcademicRecord(
        student_id=student_id,
        section_id=data.section_id,
        branch_id=data.branch_id,
        academic_year_id=data.academic_year_id,
        status=StudentStatus.ACTIVE,
    )
    db.add(record)
    await db.flush()
    await db.refresh(record)
    return record


async def list_academic_records(db: AsyncSession, student_id: str):
    student = await get_student(db, student_id)
    result = await db.execute(
        select(StudentAcademicRecord)
        .where(StudentAcademicRecord.student_id == student.id)
        .order_by(StudentAcademicRecord.enrolled_at.desc())
    )
    return result.scalars().all()


async def update_student_status(db: AsyncSession, student_id: str, status: StudentStatus) -> StudentAcademicRecord:
    student = await get_student(db, student_id)
    record = (
        await db.execute(
            select(StudentAcademicRecord)
            .where(
                StudentAcademicRecord.student_id == student.id,
                StudentAcademicRecord.exited_at == None,
            )
            .order_by(StudentAcademicRecord.enrolled_at.desc())
        )
    ).scalar_one_or_none()
    if not record:
        raise NotFoundError("Active academic record not found")
    record.status = status
    if status in (StudentStatus.TRANSFERRED, StudentStatus.GRADUATED, StudentStatus.DROPPED):
        record.exited_at = datetime.now(timezone.utc)
    elif status == StudentStatus.ACTIVE:
        record.exited_at = None
    await db.flush()
    return record


async def list_documents(db: AsyncSession, institution_id: str, offset: int, limit: int):
    q = (
        select(StudentDocument, User.full_name, Student.roll_number)
        .join(Student, Student.id == StudentDocument.student_id)
        .join(User, User.id == Student.user_id)
        .where(User.institution_id == institution_id)
        .order_by(StudentDocument.created_at.desc())
    )
    total_q = (
        select(func.count(StudentDocument.id))
        .join(Student, Student.id == StudentDocument.student_id)
        .join(User, User.id == Student.user_id)
        .where(User.institution_id == institution_id)
    )
    total = (await db.execute(total_q)).scalar() or 0
    rows = (await db.execute(q.offset(offset).limit(limit))).all()
    return rows, total


async def create_document(db: AsyncSession, data: StudentDocumentCreate) -> StudentDocument:
    await get_student(db, str(data.student_id))
    item = StudentDocument(**data.model_dump())
    db.add(item)
    await db.flush()
    await db.refresh(item)
    return item


async def update_document(db: AsyncSession, document_id: str, data: StudentDocumentUpdate) -> StudentDocument:
    item = (
        await db.execute(select(StudentDocument).where(StudentDocument.id == document_id))
    ).scalar_one_or_none()
    if not item:
        raise NotFoundError("Student document not found")
    for key, value in data.model_dump(exclude_none=True).items():
        setattr(item, key, value)
    await db.flush()
    return item


async def delete_document(db: AsyncSession, document_id: str) -> None:
    item = (
        await db.execute(select(StudentDocument).where(StudentDocument.id == document_id))
    ).scalar_one_or_none()
    if not item:
        raise NotFoundError("Student document not found")
    await db.delete(item)
    await db.flush()
