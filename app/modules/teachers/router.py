from typing import Annotated
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.session import get_db
from app.modules.teachers import service
from app.modules.teachers.model import TimetableDay
from app.modules.teachers.schema import (
    TeacherCreate,
    TeacherOut,
    SubjectAssignRequest,
    TeacherClassAssignRequest,
    TeacherClassOut,
    TeacherCandidateOut,
    TeacherTimetableCreate,
    TeacherTimetableUpdate,
    TeacherTimetableOut,
)
from app.modules.users.model import User
from app.core.dependencies import CurrentUser, require_permission
from app.constants.permissions import TEACHER_CREATE, TEACHER_READ, TEACHER_UPDATE
from app.utils.response import ok, paginated
from app.utils.pagination import PaginationParams

router = APIRouter(prefix="/teachers", tags=["Teachers"])
DB = Annotated[AsyncSession, Depends(get_db)]


@router.post("", response_model=dict, dependencies=[Depends(require_permission(TEACHER_CREATE))])
async def create_teacher(payload: TeacherCreate, current_user: CurrentUser, db: DB):
    teacher = await service.create_teacher(
        db,
        payload,
        actor_institution_id=current_user["institution_id"],
    )
    return ok(data={"id": str(teacher.id)}, message="Teacher created")


@router.get("/candidates", response_model=dict, dependencies=[Depends(require_permission(TEACHER_READ))])
async def list_teacher_candidates(current_user: CurrentUser, db: DB):
    users = await service.list_teacher_candidates(db, current_user["institution_id"])
    items = [
        TeacherCandidateOut(
            user_id=user.id,
            institution_id=user.institution_id,
            full_name=user.full_name,
            email=user.email,
            username=user.username,
            phone=user.phone,
        ).model_dump()
        for user in users
    ]
    return ok(data=items)


@router.get("", response_model=dict, dependencies=[Depends(require_permission(TEACHER_READ))])
async def list_teachers(current_user: CurrentUser, db: DB, pagination: Annotated[PaginationParams, Depends()]):
    teachers, total = await service.list_teachers(db, current_user["institution_id"], pagination.offset, pagination.page_size)
    out = []
    for t in teachers:
        user = (await db.execute(select(User).where(User.id == t.user_id))).scalar_one()
        out.append(
            TeacherOut(
                id=t.id,
                user_id=t.user_id,
                employee_code=t.employee_code,
                designation=t.designation,
                joined_at=t.joined_at,
                full_name=user.full_name,
                email=user.email,
                username=user.username,
                phone=user.phone,
                assigned_classes=[
                    TeacherClassOut(**item)
                    for item in await service.list_teacher_classes(db, str(t.id))
                ],
            ).model_dump()
        )
    return paginated(out, total, pagination.page, pagination.page_size)


@router.get("/{teacher_id}", response_model=dict, dependencies=[Depends(require_permission(TEACHER_READ))])
async def get_teacher(teacher_id: str, db: DB):
    teacher = await service.get_teacher(db, teacher_id)
    user = (await db.execute(select(User).where(User.id == teacher.user_id))).scalar_one()
    data = TeacherOut(
        id=teacher.id,
        user_id=teacher.user_id,
        employee_code=teacher.employee_code,
        designation=teacher.designation,
        joined_at=teacher.joined_at,
        full_name=user.full_name,
        email=user.email,
        username=user.username,
        phone=user.phone,
        assigned_classes=[
            TeacherClassOut(**item)
            for item in await service.list_teacher_classes(db, teacher_id)
        ],
    ).model_dump()
    return ok(data=data)


@router.post("/{teacher_id}/subjects", response_model=dict, dependencies=[Depends(require_permission(TEACHER_UPDATE))])
async def assign_subject(teacher_id: str, payload: SubjectAssignRequest, db: DB):
    ts = await service.assign_subject(db, teacher_id, payload)
    return ok(data={"id": str(ts.id)}, message="Subject assigned")


@router.get("/{teacher_id}/classes", response_model=dict, dependencies=[Depends(require_permission(TEACHER_READ))])
async def list_teacher_classes(teacher_id: str, db: DB):
    items = await service.list_teacher_classes(db, teacher_id)
    return ok(data=[TeacherClassOut(**item).model_dump() for item in items])


@router.post("/{teacher_id}/classes", response_model=dict, dependencies=[Depends(require_permission(TEACHER_UPDATE))])
async def assign_class(teacher_id: str, payload: TeacherClassAssignRequest, db: DB):
    link = await service.assign_class(db, teacher_id, payload)
    return ok(data={"id": str(link.id)}, message="Class linked to teacher")


@router.delete("/{teacher_id}/classes/{class_id}", response_model=dict, dependencies=[Depends(require_permission(TEACHER_UPDATE))])
async def remove_class(teacher_id: str, class_id: str, db: DB):
    await service.remove_class(db, teacher_id, class_id)
    return ok(message="Class unlinked from teacher")


@router.get("/{teacher_id}/timetable", response_model=dict, dependencies=[Depends(require_permission(TEACHER_READ))])
async def list_teacher_timetable(teacher_id: str, db: DB, day_of_week: TimetableDay | None = None):
    items = await service.list_teacher_timetable(db, teacher_id, day_of_week=day_of_week)
    return ok(data=[TeacherTimetableOut(**item).model_dump() for item in items])


@router.post("/{teacher_id}/timetable", response_model=dict, dependencies=[Depends(require_permission(TEACHER_UPDATE))])
async def create_teacher_timetable(teacher_id: str, payload: TeacherTimetableCreate, db: DB):
    item = await service.create_timetable_entry(db, teacher_id, payload)
    return ok(data={"id": str(item.id)}, message="Timetable entry created")


@router.patch("/timetable/{entry_id}", response_model=dict, dependencies=[Depends(require_permission(TEACHER_UPDATE))])
async def update_teacher_timetable(entry_id: str, payload: TeacherTimetableUpdate, db: DB):
    item = await service.update_timetable_entry(db, entry_id, payload)
    return ok(data={"id": str(item.id)}, message="Timetable entry updated")


@router.delete("/timetable/{entry_id}", response_model=dict, dependencies=[Depends(require_permission(TEACHER_UPDATE))])
async def delete_teacher_timetable(entry_id: str, db: DB):
    await service.delete_timetable_entry(db, entry_id)
    return ok(message="Timetable entry deleted")
