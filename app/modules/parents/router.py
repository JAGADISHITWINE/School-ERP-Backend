from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import CurrentUser
from app.db.session import get_db
from app.modules.parents import service
from app.utils.response import ok

router = APIRouter(prefix="/parents", tags=["Parent Portal"])
DB = Annotated[AsyncSession, Depends(get_db)]


@router.get("/self/portal", response_model=dict)
async def get_parent_portal(current_user: CurrentUser, db: DB):
    data = await service.get_parent_portal(db, current_user)
    return ok(data=data)


@router.get("/self/children", response_model=dict)
async def get_parent_children(current_user: CurrentUser, db: DB):
    data = await service.get_parent_children(db, current_user)
    return ok(data=data)


@router.get("/self/children/{student_id}/attendance", response_model=dict)
async def get_child_attendance(student_id: str, current_user: CurrentUser, db: DB):
    await service.assert_parent_can_access_student(db, current_user, student_id)
    return ok(data=await service.get_attendance_data(db, student_id))


@router.get("/self/children/{student_id}/fees", response_model=dict)
async def get_child_fees(student_id: str, current_user: CurrentUser, db: DB):
    await service.assert_parent_can_access_student(db, current_user, student_id)
    return ok(data=await service.get_fees_data(db, student_id))


@router.get("/self/children/{student_id}/exams", response_model=dict)
async def get_child_exams(student_id: str, current_user: CurrentUser, db: DB):
    await service.assert_parent_can_access_student(db, current_user, student_id)
    return ok(data=await service.get_exams_data(db, student_id))


@router.get("/self/children/{student_id}/timetable", response_model=dict)
async def get_child_timetable(student_id: str, current_user: CurrentUser, db: DB):
    await service.assert_parent_can_access_student(db, current_user, student_id)
    return ok(data=await service.get_timetable_data(db, student_id))

