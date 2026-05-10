from typing import Annotated
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from io import StringIO
import csv
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.modules.attendance import service
from app.modules.attendance.schema import (
    SessionCreate,
    MarkAttendanceRequest,
    SessionOut,
    AttendanceRecordOut,
    AttendanceStudentOut,
    AttendanceContextItem,
    AttendanceReportItem,
)
from app.modules.teachers.model import Teacher
from app.core.dependencies import CurrentUser, require_permission
from app.core.exceptions import NotFoundError
from app.constants.permissions import ATTENDANCE_MARK, ATTENDANCE_READ
from app.utils.response import ok, paginated
from app.utils.pagination import PaginationParams
from sqlalchemy import select
from datetime import date

router = APIRouter(prefix="/attendance", tags=["Attendance"])
teacher_router = APIRouter(prefix="/teacher", tags=["Teacher Attendance"])
DB = Annotated[AsyncSession, Depends(get_db)]


async def _resolve_teacher_id(db: AsyncSession, user_id: str) -> str:
    teacher = (await db.execute(select(Teacher).where(Teacher.user_id == user_id))).scalar_one_or_none()
    if not teacher:
        raise NotFoundError("Teacher profile not found for current user")
    return str(teacher.id)


@router.post("/sessions", response_model=dict, dependencies=[Depends(require_permission(ATTENDANCE_MARK))])
async def create_session(payload: SessionCreate, current_user: CurrentUser, db: DB):
    teacher_id = (
        str(payload.teacher_id)
        if payload.teacher_id
        else await _resolve_teacher_id(db, current_user["id"])
    )
    session = await service.create_session(db, teacher_id, payload, current_user["id"])
    return ok(data=SessionOut.model_validate(session).model_dump(), message="Session created")


@router.get("/sessions", response_model=dict, dependencies=[Depends(require_permission(ATTENDANCE_READ))])
async def list_sessions(section_id: str, db: DB, pagination: Annotated[PaginationParams, Depends()]):
    sessions, total = await service.list_sessions(db, section_id, pagination.offset, pagination.page_size)
    return paginated(
        [SessionOut.model_validate(s).model_dump() for s in sessions],
        total, pagination.page, pagination.page_size
    )


@router.post("/mark", response_model=dict, dependencies=[Depends(require_permission(ATTENDANCE_MARK))])
async def mark_attendance(payload: MarkAttendanceRequest, current_user: CurrentUser, db: DB):
    count = await service.mark_attendance(db, payload, current_user["id"])
    return ok(data={"records_saved": count}, message="Attendance marked")


@router.put("/update", response_model=dict, dependencies=[Depends(require_permission(ATTENDANCE_MARK))])
async def update_attendance(payload: MarkAttendanceRequest, current_user: CurrentUser, db: DB):
    count = await service.mark_attendance(db, payload, current_user["id"])
    return ok(data={"records_saved": count}, message="Attendance updated")


@router.patch("/sessions/{session_id}/close", response_model=dict, dependencies=[Depends(require_permission(ATTENDANCE_MARK))])
async def close_session(session_id: str, db: DB):
    session = await service.close_session(db, session_id)
    return ok(data=SessionOut.model_validate(session).model_dump(), message="Session closed")


@router.patch("/sessions/{session_id}/lock", response_model=dict, dependencies=[Depends(require_permission(ATTENDANCE_MARK))])
async def lock_session(session_id: str, current_user: CurrentUser, db: DB):
    session = await service.lock_session(db, session_id, current_user["id"])
    return ok(data=SessionOut.model_validate(session).model_dump(), message="Session locked")


@router.get("/sessions/{session_id}/records", response_model=dict, dependencies=[Depends(require_permission(ATTENDANCE_READ))])
async def get_session_records(session_id: str, db: DB):
    records = await service.get_session_records(db, session_id)
    return ok(data=[AttendanceRecordOut.model_validate(r).model_dump() for r in records])


@router.get("/my-context", response_model=dict, dependencies=[Depends(require_permission(ATTENDANCE_READ))])
async def my_attendance_context(current_user: CurrentUser, db: DB, target_date: date):
    context = await service.get_teacher_attendance_context(db, current_user["id"], target_date)
    return ok(
        data={
            "teacher_id": context["teacher_id"],
            "date": context["date"],
            "items": [AttendanceContextItem(**item).model_dump() for item in context["items"]],
        }
    )


@router.get("/teacher-context", response_model=dict, dependencies=[Depends(require_permission(ATTENDANCE_READ))])
async def teacher_attendance_context(teacher_id: str, db: DB, target_date: date):
    context = await service.get_teacher_attendance_context_by_teacher_id(db, teacher_id, target_date)
    return ok(
        data={
            "teacher_id": context["teacher_id"],
            "date": context["date"],
            "items": [AttendanceContextItem(**item).model_dump() for item in context["items"]],
        }
    )


@router.get("/section-students", response_model=dict, dependencies=[Depends(require_permission(ATTENDANCE_READ))])
async def get_section_students(section_id: str, academic_year_id: str, db: DB, session_id: str | None = None):
    items = await service.list_section_students(db, section_id, academic_year_id, session_id)
    return ok(data=[AttendanceStudentOut(**item).model_dump() for item in items])


@router.get("/class-students", response_model=dict, dependencies=[Depends(require_permission(ATTENDANCE_READ))])
async def get_class_students(section_id: str, academic_year_id: str, db: DB, session_id: str | None = None):
    items = await service.list_section_students(db, section_id, academic_year_id, session_id)
    return ok(data=[AttendanceStudentOut(**item).model_dump() for item in items])


@router.get("/report", response_model=dict, dependencies=[Depends(require_permission(ATTENDANCE_READ))])
async def get_attendance_report(section_id: str, academic_year_id: str, db: DB):
    items = await service.attendance_report(db, section_id, academic_year_id)
    return ok(data=[AttendanceReportItem(**item).model_dump() for item in items])


@router.get("/report/export", response_model=None, dependencies=[Depends(require_permission(ATTENDANCE_READ))])
async def export_attendance_report(section_id: str, academic_year_id: str, db: DB):
    items = await service.attendance_report(db, section_id, academic_year_id)
    stream = StringIO()
    writer = csv.writer(stream)
    writer.writerow(["Roll Number", "Student", "Present", "Absent", "Late", "Excused", "Percentage"])
    for row in items:
        writer.writerow([row["roll_number"], row["full_name"], row["present"], row["absent"], row["late"], row["excused"], row["percentage"]])
    stream.seek(0)
    return StreamingResponse(
        iter([stream.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=attendance_report.csv"},
    )


@router.get("/report/pdf-ready", response_model=dict, dependencies=[Depends(require_permission(ATTENDANCE_READ))])
async def attendance_report_pdf_ready(section_id: str, academic_year_id: str, db: DB):
    items = await service.attendance_report(db, section_id, academic_year_id)
    return ok(data={"title": "Attendance Report", "section_id": section_id, "academic_year_id": academic_year_id, "rows": items})


@router.get("/analytics/heatmap", response_model=dict, dependencies=[Depends(require_permission(ATTENDANCE_READ))])
async def attendance_heatmap(section_id: str, academic_year_id: str, month: int, year: int, db: DB):
    items = await service.attendance_heatmap(db, section_id, academic_year_id, month, year)
    return ok(data=items)


@router.get("/analytics/teacher-workload", response_model=dict, dependencies=[Depends(require_permission(ATTENDANCE_READ))])
async def teacher_workload(academic_year_id: str, db: DB):
    items = await service.teacher_workload_stats(db, academic_year_id)
    return ok(data=items)


@teacher_router.get("/my-timetable", response_model=dict, dependencies=[Depends(require_permission(ATTENDANCE_READ))])
async def teacher_my_timetable(current_user: CurrentUser, db: DB):
    context = await service.get_teacher_attendance_context(db, current_user["id"], date.today())
    return ok(data=context["items"])


@teacher_router.get("/today-classes", response_model=dict, dependencies=[Depends(require_permission(ATTENDANCE_READ))])
async def teacher_today_classes(current_user: CurrentUser, db: DB):
    context = await service.get_teacher_attendance_context(db, current_user["id"], date.today())
    return ok(data=context["items"])
