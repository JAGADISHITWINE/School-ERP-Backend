from typing import Annotated
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.session import get_db
from app.modules.students import service
from app.modules.students.schema import StudentCreate, StudentUpdate, AcademicRecordCreate, StudentOut, AcademicRecordOut, AcademicRecordListItem
from app.modules.users.model import User
from app.modules.students.model import StudentAcademicRecord
from app.modules.academic.model import Branch, Class, Section, AcademicYear
from app.modules.roles.model import Role, UserRole
from app.core.dependencies import CurrentUser, require_permission
from app.constants.permissions import STUDENT_CREATE, STUDENT_READ, STUDENT_UPDATE
from app.utils.response import ok, paginated
from app.utils.pagination import PaginationParams

router = APIRouter(prefix="/students", tags=["Students"])

DB = Annotated[AsyncSession, Depends(get_db)]
Pagination = Annotated[PaginationParams, Depends()]


async def _current_academic_snapshot(db: AsyncSession, student_id):
    row = (
        await db.execute(
            select(
                StudentAcademicRecord.branch_id,
                Branch.name,
                StudentAcademicRecord.section_id,
                Section.name,
                Class.id,
                Class.name,
                StudentAcademicRecord.academic_year_id,
                AcademicYear.label,
                StudentAcademicRecord.status,
            )
            .join(Branch, Branch.id == StudentAcademicRecord.branch_id)
            .join(Section, Section.id == StudentAcademicRecord.section_id)
            .join(Class, Class.id == Section.class_id)
            .join(AcademicYear, AcademicYear.id == StudentAcademicRecord.academic_year_id)
            .where(
                StudentAcademicRecord.student_id == student_id,
                StudentAcademicRecord.exited_at == None,
            )
            .limit(1)
        )
    ).first()
    if not row:
        return {}
    return {
        "current_branch_id": str(row[0]) if row[0] else None,
        "current_branch_name": row[1],
        "current_section_id": str(row[2]) if row[2] else None,
        "current_section_name": row[3],
        "current_class_id": str(row[4]) if row[4] else None,
        "current_class_name": row[5],
        "current_academic_year_id": str(row[6]) if row[6] else None,
        "current_academic_year_label": row[7],
        "current_status": row[8],
    }


async def _user_role_slug(db: AsyncSession, user_id):
    row = (
        await db.execute(
            select(Role.slug)
            .join(UserRole, UserRole.role_id == Role.id)
            .where(UserRole.user_id == user_id)
            .limit(1)
        )
    ).first()
    return row[0] if row else None


@router.post("", response_model=dict, dependencies=[Depends(require_permission(STUDENT_CREATE))])
async def create_student(payload: StudentCreate, db: DB):
    student = await service.create_student(db, payload)
    return ok(data={"id": str(student.id)}, message="Student created")


@router.get("", response_model=dict, dependencies=[Depends(require_permission(STUDENT_READ))])
async def list_students(current_user: CurrentUser, db: DB, pagination: Pagination):
    students, total = await service.list_students(
        db, current_user["institution_id"], pagination.offset, pagination.page_size
    )
    out = []
    for s in students:
        user = (await db.execute(select(User).where(User.id == s.user_id))).scalar_one()
        current = await _current_academic_snapshot(db, s.id)
        role_slug = await _user_role_slug(db, s.user_id)
        d = {
            "id": str(s.id),
            "user_id": str(s.user_id),
            "roll_number": s.roll_number,
            "date_of_birth": s.date_of_birth,
            "gender": s.gender,
            "guardian_name": s.guardian_name,
            "guardian_phone": s.guardian_phone,
            "full_name": user.full_name,
            "email": user.email,
            "role_slug": role_slug,
            "created_at": s.created_at,
            **current,
        }
        out.append(d)
    return paginated(out, total, pagination.page, pagination.page_size)


@router.get("/{student_id}", response_model=dict, dependencies=[Depends(require_permission(STUDENT_READ))])
async def get_student(student_id: str, db: DB):
    student = await service.get_student(db, student_id)
    user = (await db.execute(select(User).where(User.id == student.user_id))).scalar_one()
    current = await _current_academic_snapshot(db, student.id)
    role_slug = await _user_role_slug(db, student.user_id)
    d = {
        "id": str(student.id),
        "user_id": str(student.user_id),
        "roll_number": student.roll_number,
        "date_of_birth": student.date_of_birth,
        "gender": student.gender,
        "guardian_name": student.guardian_name,
        "guardian_phone": student.guardian_phone,
        "full_name": user.full_name,
        "email": user.email,
        "role_slug": role_slug,
        "created_at": student.created_at,
        **current,
    }
    return ok(data=d)


@router.patch("/{student_id}", response_model=dict, dependencies=[Depends(require_permission(STUDENT_UPDATE))])
async def update_student(student_id: str, payload: StudentUpdate, db: DB):
    student = await service.update_student(db, student_id, payload)
    return ok(data={"id": str(student.id)}, message="Student updated")


@router.post("/{student_id}/academic-record", response_model=dict, dependencies=[Depends(require_permission(STUDENT_UPDATE))])
async def add_academic_record(student_id: str, payload: AcademicRecordCreate, db: DB):
    record = await service.create_academic_record(db, student_id, payload)
    return ok(data=AcademicRecordOut.model_validate(record).model_dump(), message="Academic record added")


@router.get("/{student_id}/academic-records", response_model=dict, dependencies=[Depends(require_permission(STUDENT_READ))])
async def list_student_academic_records(student_id: str, db: DB):
    records = await service.list_academic_records(db, student_id)
    out = []
    for record in records:
        row = (
            await db.execute(
                select(
                    Branch.name,
                    Section.name,
                    Class.id,
                    Class.name,
                    AcademicYear.label,
                )
                .join(Section, Section.id == record.section_id)
                .join(Class, Class.id == Section.class_id)
                .join(Branch, Branch.id == record.branch_id)
                .join(AcademicYear, AcademicYear.id == record.academic_year_id)
                .where(StudentAcademicRecord.id == record.id)
            )
        ).first()
        out.append({
            "id": str(record.id),
            "student_id": str(record.student_id),
            "branch_id": str(record.branch_id),
            "branch_name": row[0] if row else None,
            "section_id": str(record.section_id),
            "section_name": row[1] if row else None,
            "class_id": str(row[2]) if row and row[2] else None,
            "class_name": row[3] if row else None,
            "academic_year_id": str(record.academic_year_id),
            "academic_year_label": row[4] if row else None,
            "status": record.status,
            "enrolled_at": record.enrolled_at,
            "exited_at": record.exited_at,
        })
    return ok(data=out)
