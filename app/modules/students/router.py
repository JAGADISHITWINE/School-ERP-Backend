from typing import Annotated
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.session import get_db
from app.modules.students import service
from app.modules.students.schema import StudentCreate, StudentUpdate, AcademicRecordCreate, StudentOut, AcademicRecordOut
from app.modules.users.model import User
from app.core.dependencies import CurrentUser, require_permission
from app.constants.permissions import STUDENT_CREATE, STUDENT_READ, STUDENT_UPDATE
from app.utils.response import ok, paginated
from app.utils.pagination import PaginationParams

router = APIRouter(prefix="/students", tags=["Students"])

DB = Annotated[AsyncSession, Depends(get_db)]
Pagination = Annotated[PaginationParams, Depends()]


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
        d = StudentOut.model_validate(s).model_dump()
        d["full_name"] = user.full_name
        d["email"] = user.email
        out.append(d)
    return paginated(out, total, pagination.page, pagination.page_size)


@router.get("/{student_id}", response_model=dict, dependencies=[Depends(require_permission(STUDENT_READ))])
async def get_student(student_id: str, db: DB):
    student = await service.get_student(db, student_id)
    user = (await db.execute(select(User).where(User.id == student.user_id))).scalar_one()
    d = StudentOut.model_validate(student).model_dump()
    d["full_name"] = user.full_name
    d["email"] = user.email
    return ok(data=d)


@router.patch("/{student_id}", response_model=dict, dependencies=[Depends(require_permission(STUDENT_UPDATE))])
async def update_student(student_id: str, payload: StudentUpdate, db: DB):
    student = await service.update_student(db, student_id, payload)
    return ok(data={"id": str(student.id)}, message="Student updated")


@router.post("/{student_id}/academic-record", response_model=dict, dependencies=[Depends(require_permission(STUDENT_UPDATE))])
async def add_academic_record(student_id: str, payload: AcademicRecordCreate, db: DB):
    record = await service.create_academic_record(db, student_id, payload)
    return ok(data=AcademicRecordOut.model_validate(record).model_dump(), message="Academic record added")
