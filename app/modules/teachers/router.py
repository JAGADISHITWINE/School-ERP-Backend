from typing import Annotated
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.session import get_db
from app.modules.teachers import service
from app.modules.teachers.schema import TeacherCreate, TeacherOut, SubjectAssignRequest
from app.modules.users.model import User
from app.core.dependencies import CurrentUser, require_permission
from app.constants.permissions import TEACHER_CREATE, TEACHER_READ, TEACHER_UPDATE
from app.utils.response import ok, paginated
from app.utils.pagination import PaginationParams

router = APIRouter(prefix="/teachers", tags=["Teachers"])
DB = Annotated[AsyncSession, Depends(get_db)]


@router.post("", response_model=dict, dependencies=[Depends(require_permission(TEACHER_CREATE))])
async def create_teacher(payload: TeacherCreate, db: DB):
    teacher = await service.create_teacher(db, payload)
    return ok(data={"id": str(teacher.id)}, message="Teacher created")


@router.get("", response_model=dict, dependencies=[Depends(require_permission(TEACHER_READ))])
async def list_teachers(current_user: CurrentUser, db: DB, pagination: Annotated[PaginationParams, Depends()]):
    teachers, total = await service.list_teachers(db, current_user["institution_id"], pagination.offset, pagination.page_size)
    out = []
    for t in teachers:
        user = (await db.execute(select(User).where(User.id == t.user_id))).scalar_one()
        d = TeacherOut.model_validate(t).model_dump()
        d["full_name"] = user.full_name
        d["email"] = user.email
        out.append(d)
    return paginated(out, total, pagination.page, pagination.page_size)


@router.post("/{teacher_id}/subjects", response_model=dict, dependencies=[Depends(require_permission(TEACHER_UPDATE))])
async def assign_subject(teacher_id: str, payload: SubjectAssignRequest, db: DB):
    ts = await service.assign_subject(db, teacher_id, payload)
    return ok(data={"id": str(ts.id)}, message="Subject assigned")
