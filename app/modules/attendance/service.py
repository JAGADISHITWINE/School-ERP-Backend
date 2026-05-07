from datetime import date
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, insert, delete
from app.modules.attendance.model import AttendanceSession, AttendanceRecord, SessionStatus
from app.modules.attendance.schema import SessionCreate, MarkAttendanceRequest
from app.modules.teachers.model import Teacher, TeacherSubject, TeacherTimetable, TimetableDay
from app.modules.students.model import Student, StudentAcademicRecord, StudentStatus
from app.modules.users.model import User
from app.modules.academic.model import Section, Class, Branch, Subject, AcademicYear
from app.core.exceptions import NotFoundError, ConflictError, BusinessRuleError, ValidationError


async def create_session(
    db: AsyncSession, teacher_id: str, data: SessionCreate
) -> AttendanceSession:
    teacher = await _get_teacher(db, teacher_id)
    section_id, subject_id, academic_year_id, timetable_id = await _resolve_session_scope(
        db, teacher.id, data
    )

    ex = (
        await db.execute(
            select(AttendanceSession).where(
                AttendanceSession.section_id == section_id,
                AttendanceSession.subject_id == subject_id,
                AttendanceSession.session_date == data.session_date,
            )
        )
    ).scalar_one_or_none()
    if ex:
        raise ConflictError("Attendance session already exists for this date")

    session = AttendanceSession(
        section_id=section_id,
        subject_id=subject_id,
        teacher_id=teacher.id,
        timetable_id=timetable_id,
        academic_year_id=academic_year_id,
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

    valid_students = {
        str(row[0])
        for row in (
            await db.execute(
                select(StudentAcademicRecord.student_id).where(
                    StudentAcademicRecord.section_id == session.section_id,
                    StudentAcademicRecord.academic_year_id == session.academic_year_id,
                    StudentAcademicRecord.exited_at == None,
                    StudentAcademicRecord.status == StudentStatus.ACTIVE,
                )
            )
        ).all()
    }

    for entry in data.records:
        if str(entry.student_id) not in valid_students:
            raise ValidationError("One or more students are not active in this section")

    await db.execute(delete(AttendanceRecord).where(AttendanceRecord.session_id == data.session_id))
    records = [
        {
            "session_id": data.session_id,
            "student_id": entry.student_id,
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


async def get_teacher_attendance_context(
    db: AsyncSession, user_id: str, target_date: date
) -> dict:
    teacher = (
        await db.execute(select(Teacher).where(Teacher.user_id == user_id))
    ).scalar_one_or_none()
    if not teacher:
        raise NotFoundError("Teacher profile not found for current user")

    return await get_teacher_attendance_context_by_teacher_id(db, str(teacher.id), target_date)


async def get_teacher_attendance_context_by_teacher_id(
    db: AsyncSession, teacher_id: str, target_date: date
) -> dict:
    teacher = await _get_teacher(db, teacher_id)

    day_name = TimetableDay(target_date.strftime("%A").lower())
    rows = (
        await db.execute(
            select(
                TeacherTimetable.id.label("timetable_id"),
                TeacherTimetable.teacher_id,
                TeacherTimetable.class_id,
                Class.name.label("class_name"),
                TeacherTimetable.section_id,
                Section.name.label("section_name"),
                TeacherTimetable.subject_id,
                Subject.name.label("subject_name"),
                TeacherTimetable.academic_year_id,
                AcademicYear.label.label("academic_year_label"),
                Branch.name.label("branch_name"),
                TeacherTimetable.day_of_week,
                TeacherTimetable.start_time,
                TeacherTimetable.end_time,
                TeacherTimetable.room_no,
                AttendanceSession.id.label("session_id"),
                AttendanceSession.status.label("session_status"),
                AttendanceSession.session_date,
            )
            .join(Class, Class.id == TeacherTimetable.class_id)
            .join(Section, Section.id == TeacherTimetable.section_id)
            .join(Subject, Subject.id == TeacherTimetable.subject_id)
            .join(Branch, Branch.id == Class.branch_id)
            .join(AcademicYear, AcademicYear.id == TeacherTimetable.academic_year_id)
            .outerjoin(
                AttendanceSession,
                (AttendanceSession.timetable_id == TeacherTimetable.id)
                & (AttendanceSession.session_date == target_date),
            )
            .where(
                TeacherTimetable.teacher_id == teacher.id,
                TeacherTimetable.day_of_week == day_name,
            )
            .order_by(TeacherTimetable.start_time.asc())
        )
    ).mappings().all()

    items = []
    for row in rows:
        item = dict(row)
        item["start_time"] = item["start_time"].strftime("%H:%M")
        item["end_time"] = item["end_time"].strftime("%H:%M")
        items.append(item)

    return {
        "teacher_id": str(teacher.id),
        "date": target_date,
        "items": items,
    }


async def list_section_students(
    db: AsyncSession,
    section_id: str,
    academic_year_id: str,
    session_id: str | None = None,
) -> list[dict]:
    existing_records = {}
    if session_id:
        rows = (
            await db.execute(
                select(
                    AttendanceRecord.student_id,
                    AttendanceRecord.status,
                    AttendanceRecord.remarks,
                ).where(AttendanceRecord.session_id == session_id)
            )
        ).all()
        existing_records = {
            str(student_id): {"status": status, "remarks": remarks}
            for student_id, status, remarks in rows
        }

    rows = (
        await db.execute(
            select(Student.id, Student.roll_number, User.full_name)
            .join(StudentAcademicRecord, StudentAcademicRecord.student_id == Student.id)
            .join(User, User.id == Student.user_id)
            .where(
                StudentAcademicRecord.section_id == section_id,
                StudentAcademicRecord.academic_year_id == academic_year_id,
                StudentAcademicRecord.exited_at == None,
                StudentAcademicRecord.status == StudentStatus.ACTIVE,
            )
            .order_by(Student.roll_number.asc(), User.full_name.asc())
        )
    ).all()

    items = []
    for student_id, roll_number, full_name in rows:
        saved = existing_records.get(str(student_id), {})
        items.append(
            {
                "student_id": student_id,
                "roll_number": roll_number,
                "full_name": full_name,
                "status": saved.get("status"),
                "remarks": saved.get("remarks"),
            }
        )
    return items


async def _get_teacher(db: AsyncSession, teacher_id: str) -> Teacher:
    teacher = (
        await db.execute(select(Teacher).where(Teacher.id == teacher_id))
    ).scalar_one_or_none()
    if not teacher:
        raise NotFoundError("Teacher not found")
    return teacher


async def _resolve_session_scope(
    db: AsyncSession,
    teacher_id,
    data: SessionCreate,
):
    if data.timetable_id:
        timetable = (
            await db.execute(
                select(TeacherTimetable).where(
                    TeacherTimetable.id == data.timetable_id,
                    TeacherTimetable.teacher_id == teacher_id,
                )
            )
        ).scalar_one_or_none()
        if not timetable:
            raise ValidationError("Timetable entry not found for this teacher")
        return (
            timetable.section_id,
            timetable.subject_id,
            timetable.academic_year_id,
            timetable.id,
        )

    if not data.section_id or not data.subject_id or not data.academic_year_id:
        raise ValidationError(
            "Provide timetable_id or section_id, subject_id, and academic_year_id"
        )

    teacher_subject = (
        await db.execute(
            select(TeacherSubject).where(
                TeacherSubject.teacher_id == teacher_id,
                TeacherSubject.section_id == data.section_id,
                TeacherSubject.subject_id == data.subject_id,
                TeacherSubject.academic_year_id == data.academic_year_id,
            )
        )
    ).scalar_one_or_none()
    if not teacher_subject:
        raise ValidationError("Teacher is not assigned to this section and subject")

    return data.section_id, data.subject_id, data.academic_year_id, None
