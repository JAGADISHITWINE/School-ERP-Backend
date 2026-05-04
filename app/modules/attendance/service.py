from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, insert, delete
from app.modules.attendance.model import AttendanceSession, AttendanceRecord, SessionStatus
from app.modules.attendance.schema import SessionCreate, MarkAttendanceRequest
from app.core.exceptions import NotFoundError, ConflictError, BusinessRuleError


async def create_session(db: AsyncSession, teacher_id: str, data: SessionCreate) -> AttendanceSession:
    ex = (
        await db.execute(
            select(AttendanceSession).where(
                AttendanceSession.section_id == data.section_id,
                AttendanceSession.subject_id == data.subject_id,
                AttendanceSession.session_date == data.session_date,
            )
        )
    ).scalar_one_or_none()
    if ex:
        raise ConflictError("Attendance session already exists for this date")

    session = AttendanceSession(
        section_id=str(data.section_id),
        subject_id=str(data.subject_id),
        teacher_id=teacher_id,
        academic_year_id=str(data.academic_year_id),
        session_date=data.session_date,
    )
    db.add(session)
    await db.flush()
    await db.refresh(session)
    return session


async def mark_attendance(db: AsyncSession, data: MarkAttendanceRequest) -> int:
    session = (
        await db.execute(select(AttendanceSession).where(AttendanceSession.id == data.session_id))
    ).scalar_one_or_none()
    if not session:
        raise NotFoundError("Attendance session not found")
    if session.status == SessionStatus.CLOSED:
        raise BusinessRuleError("Cannot modify a closed attendance session")

    await db.execute(
        delete(AttendanceRecord).where(AttendanceRecord.session_id == data.session_id)
    )
    records = [
        {
            "session_id": str(data.session_id),
            "student_id": str(entry.student_id),
            "status": entry.status,
            "remarks": entry.remarks,
        }
        for entry in data.records
    ]
    if records:
        await db.execute(insert(AttendanceRecord), records)
    await db.flush()
    return len(records)


async def close_session(db: AsyncSession, session_id: str) -> AttendanceSession:
    session = (
        await db.execute(select(AttendanceSession).where(AttendanceSession.id == session_id))
    ).scalar_one_or_none()
    if not session:
        raise NotFoundError("Session not found")
    session.status = SessionStatus.CLOSED
    await db.flush()
    return session


async def get_session_records(db: AsyncSession, session_id: str) -> list[AttendanceRecord]:
    result = await db.execute(
        select(AttendanceRecord).where(AttendanceRecord.session_id == session_id)
    )
    return result.scalars().all()


async def list_sessions(db: AsyncSession, section_id: str, offset: int, limit: int):
    q = select(AttendanceSession).where(AttendanceSession.section_id == section_id)
    total = (await db.execute(select(func.count()).select_from(q.subquery()))).scalar()
    result = await db.execute(
        q.order_by(AttendanceSession.session_date.desc()).offset(offset).limit(limit)
    )
    return result.scalars().all(), total
