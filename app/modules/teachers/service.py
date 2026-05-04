from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.modules.teachers.model import Teacher, TeacherSubject
from app.modules.users.model import User
from app.modules.teachers.schema import TeacherCreate, TeacherUpdate, SubjectAssignRequest
from app.core.security import hash_password
from app.core.exceptions import NotFoundError, ConflictError


async def create_teacher(db: AsyncSession, data: TeacherCreate) -> Teacher:
    ex = (await db.execute(select(User).where(User.email == data.email))).scalar_one_or_none()
    if ex:
        raise ConflictError("Email already registered")
    ex_code = (await db.execute(select(Teacher).where(Teacher.employee_code == data.employee_code))).scalar_one_or_none()
    if ex_code:
        raise ConflictError("Employee code already in use")

    user = User(
        institution_id=data.institution_id,
        email=data.email,
        username=data.username,
        password_hash=hash_password(data.password),
        full_name=data.full_name,
        phone=data.phone,
    )
    db.add(user); await db.flush()

    teacher = Teacher(
        user_id=user.id,
        employee_code=data.employee_code,
        designation=data.designation,
        joined_at=data.joined_at,
    )
    db.add(teacher); await db.flush(); await db.refresh(teacher)
    return teacher


async def list_teachers(db: AsyncSession, institution_id: str, offset: int, limit: int):
    q = select(Teacher).join(User, Teacher.user_id == User.id).where(User.institution_id == institution_id)
    total = (await db.execute(select(func.count()).select_from(q.subquery()))).scalar()
    result = await db.execute(q.offset(offset).limit(limit))
    return result.scalars().all(), total


async def get_teacher(db: AsyncSession, teacher_id: str) -> Teacher:
    obj = (await db.execute(select(Teacher).where(Teacher.id == teacher_id))).scalar_one_or_none()
    if not obj:
        raise NotFoundError("Teacher not found")
    return obj


async def assign_subject(db: AsyncSession, teacher_id: str, data: SubjectAssignRequest) -> TeacherSubject:
    ts = TeacherSubject(
        teacher_id=teacher_id,
        subject_id=str(data.subject_id),
        section_id=str(data.section_id),
        academic_year_id=str(data.academic_year_id),
    )
    db.add(ts); await db.flush(); await db.refresh(ts)
    return ts
