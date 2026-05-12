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
from app.modules.attendance.model import AttendanceSession
from app.modules.academic.model import Class, Section
from app.modules.teachers.model import (
    Teacher,
    TeacherClass,
    TeacherSubject,
    TeacherTimetable,
    HODLink,
    TeacherHODSubjectLink,
)
from app.core.dependencies import CurrentUser, require_permission
from app.core.exceptions import NotFoundError, ForbiddenError
from app.core.role_context import has_any_role
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


async def _assert_can_use_teacher_scope(db: AsyncSession, current_user: dict, teacher_id: str) -> None:
    if current_user.get("is_superuser") or has_any_role(current_user, {"superadmin", "admin", "principal"}):
        return

    actor_teacher = (
        await db.execute(select(Teacher).where(Teacher.user_id == current_user["id"]))
    ).scalar_one_or_none()
    if not actor_teacher:
        raise ForbiddenError("Teacher profile not found for current user")
    if str(actor_teacher.id) == str(teacher_id):
        return

    if has_any_role(current_user, {"hod"}):
        managed_branch_ids = select(HODLink.branch_id).where(HODLink.hod_teacher_id == actor_teacher.id)
        linked_teacher = (
            await db.execute(
                select(TeacherHODSubjectLink.id)
                .join(HODLink, HODLink.id == TeacherHODSubjectLink.hod_link_id)
                .where(
                    HODLink.hod_teacher_id == actor_teacher.id,
                    TeacherHODSubjectLink.teacher_id == teacher_id,
                )
                .limit(1)
            )
        ).first()
        timetable_teacher = (
            await db.execute(
                select(TeacherTimetable.id)
                .join(Class, Class.id == TeacherTimetable.class_id)
                .where(
                    TeacherTimetable.teacher_id == teacher_id,
                    TeacherTimetable.is_active == True,
                    Class.branch_id.in_(managed_branch_ids),
                )
                .limit(1)
            )
        ).first()
        if linked_teacher or timetable_teacher:
            return

    raise ForbiddenError("You can access only linked teacher attendance data")


async def _assert_can_use_section_scope(db: AsyncSession, current_user: dict, section_id: str) -> None:
    if current_user.get("is_superuser") or has_any_role(current_user, {"superadmin", "admin", "principal"}):
        return

    actor_teacher = (
        await db.execute(select(Teacher).where(Teacher.user_id == current_user["id"]))
    ).scalar_one_or_none()
    if not actor_teacher:
        raise ForbiddenError("Teacher profile not found for current user")

    if has_any_role(current_user, {"hod"}):
        managed_branch_ids = select(HODLink.branch_id).where(HODLink.hod_teacher_id == actor_teacher.id)
        row = (
            await db.execute(
                select(Section.id)
                .join(Class, Class.id == Section.class_id)
                .where(Section.id == section_id, Class.branch_id.in_(managed_branch_ids))
                .limit(1)
            )
        ).first()
        if row:
            return

    subject_section = (
        await db.execute(
            select(TeacherSubject.id)
            .where(TeacherSubject.teacher_id == actor_teacher.id, TeacherSubject.section_id == section_id)
            .limit(1)
        )
    ).first()
    timetable_section = (
        await db.execute(
            select(TeacherTimetable.id)
            .where(
                TeacherTimetable.teacher_id == actor_teacher.id,
                TeacherTimetable.section_id == section_id,
                TeacherTimetable.is_active == True,
            )
            .limit(1)
        )
    ).first()
    class_section = (
        await db.execute(
            select(TeacherClass.id)
            .join(Section, Section.class_id == TeacherClass.class_id)
            .where(TeacherClass.teacher_id == actor_teacher.id, Section.id == section_id)
            .limit(1)
        )
    ).first()
    if subject_section or timetable_section or class_section:
        return

    raise ForbiddenError("You can access only linked section attendance data")


@router.post("/sessions", response_model=dict, dependencies=[Depends(require_permission(ATTENDANCE_MARK))])
async def create_session(payload: SessionCreate, current_user: CurrentUser, db: DB):
    teacher_id = (
        str(payload.teacher_id)
        if payload.teacher_id
        else await _resolve_teacher_id(db, current_user["id"])
    )
    await _assert_can_use_teacher_scope(db, current_user, teacher_id)
    session = await service.create_session(db, teacher_id, payload, current_user["id"])
    return ok(data=SessionOut.model_validate(session).model_dump(), message="Session created")


@router.get("/sessions", response_model=dict)
async def list_sessions(section_id: str, current_user: CurrentUser, db: DB, pagination: Annotated[PaginationParams, Depends()]):
    await _assert_can_use_section_scope(db, current_user, section_id)
    sessions, total = await service.list_sessions(db, section_id, pagination.offset, pagination.page_size)
    return paginated(
        [SessionOut.model_validate(s).model_dump() for s in sessions],
        total, pagination.page, pagination.page_size
    )


@router.post("/mark", response_model=dict, dependencies=[Depends(require_permission(ATTENDANCE_MARK))])
async def mark_attendance(payload: MarkAttendanceRequest, current_user: CurrentUser, db: DB):
    session = (
        await db.execute(select(AttendanceSession).where(AttendanceSession.id == payload.session_id))
    ).scalar_one_or_none()
    if not session:
        raise NotFoundError("Attendance session not found")
    await _assert_can_use_teacher_scope(db, current_user, str(session.teacher_id))
    count = await service.mark_attendance(db, payload, current_user["id"])
    return ok(data={"records_saved": count}, message="Attendance marked")


@router.put("/update", response_model=dict, dependencies=[Depends(require_permission(ATTENDANCE_MARK))])
async def update_attendance(payload: MarkAttendanceRequest, current_user: CurrentUser, db: DB):
    session = (
        await db.execute(select(AttendanceSession).where(AttendanceSession.id == payload.session_id))
    ).scalar_one_or_none()
    if not session:
        raise NotFoundError("Attendance session not found")
    await _assert_can_use_teacher_scope(db, current_user, str(session.teacher_id))
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


@router.get("/my-context", response_model=dict)
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
async def teacher_attendance_context(teacher_id: str, current_user: CurrentUser, db: DB, target_date: date):
    await _assert_can_use_teacher_scope(db, current_user, teacher_id)
    context = await service.get_teacher_attendance_context_by_teacher_id(db, teacher_id, target_date)
    return ok(
        data={
            "teacher_id": context["teacher_id"],
            "date": context["date"],
            "items": [AttendanceContextItem(**item).model_dump() for item in context["items"]],
        }
    )


@router.get("/section-students", response_model=dict)
async def get_section_students(section_id: str, academic_year_id: str, current_user: CurrentUser, db: DB, session_id: str | None = None):
    await _assert_can_use_section_scope(db, current_user, section_id)
    items = await service.list_section_students(db, section_id, academic_year_id, session_id)
    return ok(data=[AttendanceStudentOut(**item).model_dump() for item in items])


@router.get("/class-students", response_model=dict)
async def get_class_students(section_id: str, academic_year_id: str, current_user: CurrentUser, db: DB, session_id: str | None = None):
    await _assert_can_use_section_scope(db, current_user, section_id)
    items = await service.list_section_students(db, section_id, academic_year_id, session_id)
    return ok(data=[AttendanceStudentOut(**item).model_dump() for item in items])


@router.get("/report", response_model=dict, dependencies=[Depends(require_permission(ATTENDANCE_READ))])
async def get_attendance_report(section_id: str, academic_year_id: str, current_user: CurrentUser, db: DB):
    await _assert_can_use_section_scope(db, current_user, section_id)
    items = await service.attendance_report(db, section_id, academic_year_id)
    return ok(data=[AttendanceReportItem(**item).model_dump() for item in items])


@router.get("/summary", response_model=dict)
async def get_attendance_summary(
    section_id: str,
    academic_year_id: str,
    current_user: CurrentUser,
    db: DB,
    session_id: str | None = None,
    target_date: date | None = None,
    subject_id: str | None = None,
):
    await _assert_can_use_section_scope(db, current_user, section_id)
    data = await service.attendance_session_summary(
        db,
        section_id=section_id,
        academic_year_id=academic_year_id,
        session_id=session_id,
        target_date=target_date,
        subject_id=subject_id,
    )
    return ok(data=data)


@router.get("/reports/class", response_model=dict)
async def get_class_attendance_report(section_id: str, academic_year_id: str, current_user: CurrentUser, db: DB):
    await _assert_can_use_section_scope(db, current_user, section_id)
    return ok(data=await service.class_attendance_report(db, section_id, academic_year_id))


@router.get("/reports/subject", response_model=dict)
async def get_subject_attendance_report(section_id: str, academic_year_id: str, subject_id: str, current_user: CurrentUser, db: DB):
    await _assert_can_use_section_scope(db, current_user, section_id)
    return ok(data=await service.subject_attendance_report(db, section_id, academic_year_id, subject_id))


@router.get("/reports/student/{student_id}", response_model=dict, dependencies=[Depends(require_permission(ATTENDANCE_READ))])
async def get_student_attendance_detail(student_id: str, db: DB, academic_year_id: str | None = None):
    return ok(data=await service.student_attendance_detail(db, student_id, academic_year_id))


@router.get("/report/export", response_model=None, dependencies=[Depends(require_permission(ATTENDANCE_READ))])
async def export_attendance_report(section_id: str, academic_year_id: str, current_user: CurrentUser, db: DB):
    await _assert_can_use_section_scope(db, current_user, section_id)
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
async def attendance_report_pdf_ready(section_id: str, academic_year_id: str, current_user: CurrentUser, db: DB):
    await _assert_can_use_section_scope(db, current_user, section_id)
    items = await service.attendance_report(db, section_id, academic_year_id)
    return ok(data={"title": "Attendance Report", "section_id": section_id, "academic_year_id": academic_year_id, "rows": items})


@router.get("/analytics/heatmap", response_model=dict)
async def attendance_heatmap(section_id: str, academic_year_id: str, month: int, year: int, current_user: CurrentUser, db: DB):
    await _assert_can_use_section_scope(db, current_user, section_id)
    items = await service.attendance_heatmap(db, section_id, academic_year_id, month, year)
    return ok(data=items)


@router.get("/analytics/monthly", response_model=dict)
async def monthly_attendance_analytics(
    section_id: str,
    academic_year_id: str,
    month: int,
    year: int,
    current_user: CurrentUser,
    db: DB,
    subject_id: str | None = None,
):
    await _assert_can_use_section_scope(db, current_user, section_id)
    data = await service.monthly_attendance_analytics(db, section_id, academic_year_id, month, year, subject_id)
    return ok(data=data)


@router.get("/analytics/teacher-workload", response_model=dict, dependencies=[Depends(require_permission(ATTENDANCE_READ))])
async def teacher_workload(academic_year_id: str, db: DB):
    items = await service.teacher_workload_stats(db, academic_year_id)
    return ok(data=items)


@teacher_router.get("/my-timetable", response_model=dict)
async def teacher_my_timetable(current_user: CurrentUser, db: DB):
    context = await service.get_teacher_attendance_context(db, current_user["id"], date.today())
    return ok(data=context["items"])


@teacher_router.get("/today-classes", response_model=dict)
async def teacher_today_classes(current_user: CurrentUser, db: DB):
    context = await service.get_teacher_attendance_context(db, current_user["id"], date.today())
    return ok(data=context["items"])
