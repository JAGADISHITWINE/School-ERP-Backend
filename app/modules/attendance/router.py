from typing import Annotated
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.modules.attendance import service
from app.modules.attendance.schema import SessionCreate, MarkAttendanceRequest, SessionOut, AttendanceRecordOut
from app.modules.teachers.model import Teacher
from app.core.dependencies import CurrentUser, require_permission
from app.constants.permissions import ATTENDANCE_MARK, ATTENDANCE_READ
from app.utils.response import ok, paginated
from app.utils.pagination import PaginationParams
from sqlalchemy import select

router = APIRouter(prefix="/attendance", tags=["Attendance"])
DB = Annotated[AsyncSession, Depends(get_db)]


async def _resolve_teacher_id(db: AsyncSession, user_id: str) -> str:
    teacher = (await db.execute(select(Teacher).where(Teacher.user_id == user_id))).scalar_one_or_none()
    if not teacher:
        raise Exception("Teacher profile not found for current user")
    return str(teacher.id)


@router.post("/sessions", response_model=dict, dependencies=[Depends(require_permission(ATTENDANCE_MARK))])
async def create_session(payload: SessionCreate, current_user: CurrentUser, db: DB):
    teacher_id = await _resolve_teacher_id(db, current_user["id"])
    session = await service.create_session(db, teacher_id, payload)
    return ok(data=SessionOut.model_validate(session).model_dump(), message="Session created")


@router.get("/sessions", response_model=dict, dependencies=[Depends(require_permission(ATTENDANCE_READ))])
async def list_sessions(section_id: str, db: DB, pagination: Annotated[PaginationParams, Depends()]):
    sessions, total = await service.list_sessions(db, section_id, pagination.offset, pagination.page_size)
    return paginated(
        [SessionOut.model_validate(s).model_dump() for s in sessions],
        total, pagination.page, pagination.page_size
    )


@router.post("/mark", response_model=dict, dependencies=[Depends(require_permission(ATTENDANCE_MARK))])
async def mark_attendance(payload: MarkAttendanceRequest, db: DB):
    count = await service.mark_attendance(db, payload)
    return ok(data={"records_saved": count}, message="Attendance marked")


@router.patch("/sessions/{session_id}/close", response_model=dict, dependencies=[Depends(require_permission(ATTENDANCE_MARK))])
async def close_session(session_id: str, db: DB):
    session = await service.close_session(db, session_id)
    return ok(data=SessionOut.model_validate(session).model_dump(), message="Session closed")


@router.get("/sessions/{session_id}/records", response_model=dict, dependencies=[Depends(require_permission(ATTENDANCE_READ))])
async def get_session_records(session_id: str, db: DB):
    records = await service.get_session_records(db, session_id)
    return ok(data=[AttendanceRecordOut.model_validate(r).model_dump() for r in records])
