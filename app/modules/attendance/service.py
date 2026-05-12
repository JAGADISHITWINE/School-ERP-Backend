from datetime import date, datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, insert, delete, case
from app.modules.attendance.model import AttendanceSession, AttendanceRecord, SessionStatus, AttendanceStatus, AttendanceAuditLog
from app.modules.attendance.schema import SessionCreate, MarkAttendanceRequest
from app.modules.teachers.model import Teacher, TeacherSubject, TeacherTimetable, TimetableDay
from app.modules.students.model import Student, StudentAcademicRecord, StudentStatus
from app.modules.users.model import User
from app.modules.academic.model import Section, Class, Branch, Subject, AcademicYear
from app.modules.notifications.service import send_absent_alerts
from app.core.exceptions import NotFoundError, ConflictError, BusinessRuleError, ValidationError


async def create_session(
    db: AsyncSession, teacher_id: str, data: SessionCreate, actor_user_id: str | None = None
) -> AttendanceSession:
    if data.session_date > date.today():
        raise ValidationError("Future-date attendance is not allowed")

    teacher = await _get_teacher(db, teacher_id)
    section_id, subject_id, academic_year_id, timetable_id = await _resolve_session_scope(
        db, teacher.id, data
    )

    ex = (
        await db.execute(
            select(AttendanceSession).where(
                AttendanceSession.timetable_id == timetable_id,
                AttendanceSession.session_date == data.session_date,
            )
        )
    ).scalar_one_or_none()
    if ex:
        raise ConflictError("Attendance already marked for this session.")

    await _validate_timing_window(db, timetable_id, data.session_date)

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
    db.add(AttendanceAuditLog(session_id=session.id, action="session_created", actor_user_id=actor_user_id))
    await db.refresh(session)
    return session


async def mark_attendance(db: AsyncSession, data: MarkAttendanceRequest, actor_user_id: str | None = None) -> int:
    session = (
        await db.execute(select(AttendanceSession).where(AttendanceSession.id == data.session_id))
    ).scalar_one_or_none()
    if not session:
        raise NotFoundError("Attendance session not found")
    if session.session_date > date.today():
        raise ValidationError("Future-date attendance is not allowed")
    if session.status in (SessionStatus.CLOSED, SessionStatus.LOCKED):
        raise BusinessRuleError("Cannot modify a closed/locked attendance session")

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
    db.add(AttendanceAuditLog(session_id=session.id, action="attendance_marked", actor_user_id=actor_user_id))
    absent_student_ids = [entry.student_id for entry in data.records if entry.status == AttendanceStatus.ABSENT]
    await send_absent_alerts(db, session=session, absent_student_ids=absent_student_ids)
    await db.flush()
    return len(records)


async def close_session(db: AsyncSession, session_id: str) -> AttendanceSession:
    session = (
        await db.execute(select(AttendanceSession).where(AttendanceSession.id == session_id))
    ).scalar_one_or_none()
    if not session:
        raise NotFoundError("Session not found")
    session.status = SessionStatus.CLOSED
    db.add(AttendanceAuditLog(session_id=session.id, action="session_closed"))
    await db.flush()
    return session


async def lock_session(db: AsyncSession, session_id: str, approver_user_id: str | None = None) -> AttendanceSession:
    session = (
        await db.execute(select(AttendanceSession).where(AttendanceSession.id == session_id))
    ).scalar_one_or_none()
    if not session:
        raise NotFoundError("Session not found")
    session.status = SessionStatus.LOCKED
    session.approved_by = approver_user_id
    session.approved_at = datetime.utcnow()
    db.add(AttendanceAuditLog(session_id=session.id, action="session_locked", actor_user_id=approver_user_id))
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


async def attendance_report(db: AsyncSession, section_id: str, academic_year_id: str):
    rows = (
        await db.execute(
            select(
                Student.id,
                Student.roll_number,
                User.full_name,
                func.sum(case((AttendanceRecord.status == AttendanceStatus.PRESENT, 1), else_=0)).label("present"),
                func.sum(case((AttendanceRecord.status == AttendanceStatus.ABSENT, 1), else_=0)).label("absent"),
                func.sum(case((AttendanceRecord.status == AttendanceStatus.LATE, 1), else_=0)).label("late"),
                func.sum(case((AttendanceRecord.status == AttendanceStatus.EXCUSED, 1), else_=0)).label("excused"),
                func.count(AttendanceRecord.id).label("total"),
            )
            .join(AttendanceRecord, AttendanceRecord.student_id == Student.id)
            .join(AttendanceSession, AttendanceSession.id == AttendanceRecord.session_id)
            .join(User, User.id == Student.user_id)
            .where(
                AttendanceSession.section_id == section_id,
                AttendanceSession.academic_year_id == academic_year_id,
            )
            .group_by(Student.id, Student.roll_number, User.full_name)
            .order_by(Student.roll_number.asc())
        )
    ).all()
    items = []
    for row in rows:
        total = row.total or 0
        pct = round(((row.present or 0) + (row.late or 0)) * 100.0 / total, 2) if total else 0.0
        items.append(
            {
                "student_id": row.id,
                "roll_number": row.roll_number,
                "full_name": row.full_name,
                "present": row.present or 0,
                "absent": row.absent or 0,
                "late": row.late or 0,
                "excused": row.excused or 0,
                "percentage": pct,
            }
        )
    return items


async def attendance_heatmap(db: AsyncSession, section_id: str, academic_year_id: str, month: int, year: int):
    rows = (
        await db.execute(
            select(
                AttendanceSession.session_date,
                func.sum(case((AttendanceRecord.status == AttendanceStatus.PRESENT, 1), else_=0)).label("present"),
                func.sum(case((AttendanceRecord.status == AttendanceStatus.LATE, 1), else_=0)).label("late"),
                func.count(AttendanceRecord.id).label("total"),
            )
            .join(AttendanceRecord, AttendanceRecord.session_id == AttendanceSession.id)
            .where(
                AttendanceSession.section_id == section_id,
                AttendanceSession.academic_year_id == academic_year_id,
                func.extract("month", AttendanceSession.session_date) == month,
                func.extract("year", AttendanceSession.session_date) == year,
            )
            .group_by(AttendanceSession.session_date)
            .order_by(AttendanceSession.session_date.asc())
        )
    ).all()
    items = []
    for row in rows:
        total = row.total or 0
        score = round(((row.present or 0) + (row.late or 0)) * 100.0 / total, 2) if total else 0.0
        items.append({"date": row.session_date, "score": score, "total": total})
    return items


async def teacher_workload_stats(db: AsyncSession, academic_year_id: str):
    rows = (
        await db.execute(
            select(
                Teacher.id.label("teacher_id"),
                User.full_name,
                func.count(func.distinct(TeacherTimetable.id)).label("timetable_slots"),
                func.count(func.distinct(AttendanceSession.id)).label("sessions_taken"),
            )
            .join(User, User.id == Teacher.user_id)
            .outerjoin(
                TeacherTimetable,
                (TeacherTimetable.teacher_id == Teacher.id)
                & (TeacherTimetable.academic_year_id == academic_year_id)
                & (TeacherTimetable.is_active == True),
            )
            .outerjoin(
                AttendanceSession,
                (AttendanceSession.teacher_id == Teacher.id)
                & (AttendanceSession.academic_year_id == academic_year_id),
            )
            .group_by(Teacher.id, User.full_name)
            .order_by(User.full_name.asc())
        )
    ).all()
    return [
        {
            "teacher_id": row.teacher_id,
            "teacher_name": row.full_name,
            "timetable_slots": int(row.timetable_slots or 0),
            "sessions_taken": int(row.sessions_taken or 0),
        }
        for row in rows
    ]


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
                "photo_url": None,
                "status": saved.get("status"),
                "remarks": saved.get("remarks"),
            }
        )
    return items


async def attendance_session_summary(
    db: AsyncSession,
    section_id: str,
    academic_year_id: str,
    session_id: str | None = None,
    target_date: date | None = None,
    subject_id: str | None = None,
) -> dict:
    total_students = (
        await db.execute(
            select(func.count(StudentAcademicRecord.student_id)).where(
                StudentAcademicRecord.section_id == section_id,
                StudentAcademicRecord.academic_year_id == academic_year_id,
                StudentAcademicRecord.exited_at == None,
                StudentAcademicRecord.status == StudentStatus.ACTIVE,
            )
        )
    ).scalar() or 0

    q = (
        select(
            func.sum(case((AttendanceRecord.status == AttendanceStatus.PRESENT, 1), else_=0)).label("present"),
            func.sum(case((AttendanceRecord.status == AttendanceStatus.ABSENT, 1), else_=0)).label("absent"),
            func.sum(case((AttendanceRecord.status == AttendanceStatus.LATE, 1), else_=0)).label("late"),
            func.sum(case((AttendanceRecord.status == AttendanceStatus.EXCUSED, 1), else_=0)).label("excused"),
            func.count(AttendanceRecord.id).label("marked"),
        )
        .select_from(AttendanceSession)
        .outerjoin(AttendanceRecord, AttendanceRecord.session_id == AttendanceSession.id)
        .where(
            AttendanceSession.section_id == section_id,
            AttendanceSession.academic_year_id == academic_year_id,
        )
    )
    if session_id:
        q = q.where(AttendanceSession.id == session_id)
    if target_date:
        q = q.where(AttendanceSession.session_date == target_date)
    if subject_id:
        q = q.where(AttendanceSession.subject_id == subject_id)

    row = (await db.execute(q)).first()
    present = int(row.present or 0) if row else 0
    absent = int(row.absent or 0) if row else 0
    late = int(row.late or 0) if row else 0
    excused = int(row.excused or 0) if row else 0
    marked = int(row.marked or 0) if row else 0
    attended = present + late
    denominator = marked if marked else total_students
    percentage = round(attended * 100.0 / denominator, 2) if denominator else 0.0
    return {
        "total_students": int(total_students),
        "present": present,
        "absent": absent,
        "late": late,
        "leave": excused,
        "marked": marked,
        "unmarked": max(int(total_students) - marked, 0),
        "percentage": percentage,
    }


async def class_attendance_report(db: AsyncSession, section_id: str, academic_year_id: str):
    return await attendance_report(db, section_id, academic_year_id)


async def subject_attendance_report(db: AsyncSession, section_id: str, academic_year_id: str, subject_id: str):
    rows = (
        await db.execute(
            select(
                Student.id,
                Student.roll_number,
                User.full_name,
                func.sum(case((AttendanceRecord.status == AttendanceStatus.PRESENT, 1), else_=0)).label("present"),
                func.sum(case((AttendanceRecord.status == AttendanceStatus.ABSENT, 1), else_=0)).label("absent"),
                func.sum(case((AttendanceRecord.status == AttendanceStatus.LATE, 1), else_=0)).label("late"),
                func.sum(case((AttendanceRecord.status == AttendanceStatus.EXCUSED, 1), else_=0)).label("excused"),
                func.count(AttendanceRecord.id).label("total"),
            )
            .join(AttendanceRecord, AttendanceRecord.student_id == Student.id)
            .join(AttendanceSession, AttendanceSession.id == AttendanceRecord.session_id)
            .join(User, User.id == Student.user_id)
            .where(
                AttendanceSession.section_id == section_id,
                AttendanceSession.academic_year_id == academic_year_id,
                AttendanceSession.subject_id == subject_id,
            )
            .group_by(Student.id, Student.roll_number, User.full_name)
            .order_by(Student.roll_number.asc())
        )
    ).all()
    return [_report_row(row) for row in rows]


async def student_attendance_detail(db: AsyncSession, student_id: str, academic_year_id: str | None = None) -> dict:
    student_row = (
        await db.execute(
            select(Student, User.full_name, User.email)
            .join(User, User.id == Student.user_id)
            .where(Student.id == student_id)
        )
    ).first()
    if not student_row:
        raise NotFoundError("Student not found")
    student, full_name, email = student_row

    filters = [AttendanceRecord.student_id == student_id]
    if academic_year_id:
        filters.append(AttendanceSession.academic_year_id == academic_year_id)

    history_rows = (
        await db.execute(
            select(
                AttendanceSession.session_date,
                AttendanceRecord.status,
                AttendanceRecord.remarks,
                Subject.name.label("subject_name"),
                Class.name.label("class_name"),
                Section.name.label("section_name"),
                AttendanceSession.id.label("session_id"),
            )
            .select_from(AttendanceRecord)
            .join(AttendanceSession, AttendanceSession.id == AttendanceRecord.session_id)
            .join(Subject, Subject.id == AttendanceSession.subject_id)
            .join(Section, Section.id == AttendanceSession.section_id)
            .join(Class, Class.id == Section.class_id)
            .where(*filters)
            .order_by(AttendanceSession.session_date.desc())
        )
    ).mappings().all()

    subject_rows = (
        await db.execute(
            select(
                Subject.id,
                Subject.name,
                func.sum(case((AttendanceRecord.status == AttendanceStatus.PRESENT, 1), else_=0)).label("present"),
                func.sum(case((AttendanceRecord.status == AttendanceStatus.ABSENT, 1), else_=0)).label("absent"),
                func.sum(case((AttendanceRecord.status == AttendanceStatus.LATE, 1), else_=0)).label("late"),
                func.sum(case((AttendanceRecord.status == AttendanceStatus.EXCUSED, 1), else_=0)).label("excused"),
                func.count(AttendanceRecord.id).label("total"),
            )
            .select_from(AttendanceRecord)
            .join(AttendanceSession, AttendanceSession.id == AttendanceRecord.session_id)
            .join(Subject, Subject.id == AttendanceSession.subject_id)
            .where(*filters)
            .group_by(Subject.id, Subject.name)
            .order_by(Subject.name.asc())
        )
    ).all()

    monthly_rows = (
        await db.execute(
            select(
                func.extract("year", AttendanceSession.session_date).label("year"),
                func.extract("month", AttendanceSession.session_date).label("month"),
                func.sum(case((AttendanceRecord.status == AttendanceStatus.PRESENT, 1), else_=0)).label("present"),
                func.sum(case((AttendanceRecord.status == AttendanceStatus.LATE, 1), else_=0)).label("late"),
                func.count(AttendanceRecord.id).label("total"),
            )
            .select_from(AttendanceRecord)
            .join(AttendanceSession, AttendanceSession.id == AttendanceRecord.session_id)
            .where(*filters)
            .group_by("year", "month")
            .order_by("year", "month")
        )
    ).all()

    total = len(history_rows)
    attended = sum(1 for row in history_rows if row["status"] in (AttendanceStatus.PRESENT, AttendanceStatus.LATE))
    percentage = round(attended * 100.0 / total, 2) if total else 0.0

    return {
        "student": {
            "id": str(student.id),
            "roll_number": student.roll_number,
            "full_name": full_name,
            "email": email,
            "photo_url": None,
        },
        "summary": {
            "total": total,
            "present": sum(1 for row in history_rows if row["status"] == AttendanceStatus.PRESENT),
            "absent": sum(1 for row in history_rows if row["status"] == AttendanceStatus.ABSENT),
            "late": sum(1 for row in history_rows if row["status"] == AttendanceStatus.LATE),
            "leave": sum(1 for row in history_rows if row["status"] == AttendanceStatus.EXCUSED),
            "percentage": percentage,
            "low_attendance": percentage < 75 if total else False,
        },
        "subjects": [_report_row(row, id_index=True) for row in subject_rows],
        "monthly": [
            {
                "year": int(row.year),
                "month": int(row.month),
                "percentage": round(((row.present or 0) + (row.late or 0)) * 100.0 / (row.total or 1), 2),
                "total": int(row.total or 0),
            }
            for row in monthly_rows
        ],
        "history": [dict(row) for row in history_rows],
    }


async def monthly_attendance_analytics(
    db: AsyncSession,
    section_id: str,
    academic_year_id: str,
    month: int,
    year: int,
    subject_id: str | None = None,
) -> dict:
    q = (
        select(
            AttendanceSession.session_date,
            func.sum(case((AttendanceRecord.status == AttendanceStatus.PRESENT, 1), else_=0)).label("present"),
            func.sum(case((AttendanceRecord.status == AttendanceStatus.ABSENT, 1), else_=0)).label("absent"),
            func.sum(case((AttendanceRecord.status == AttendanceStatus.LATE, 1), else_=0)).label("late"),
            func.sum(case((AttendanceRecord.status == AttendanceStatus.EXCUSED, 1), else_=0)).label("leave"),
            func.count(AttendanceRecord.id).label("total"),
        )
        .select_from(AttendanceSession)
        .outerjoin(AttendanceRecord, AttendanceRecord.session_id == AttendanceSession.id)
        .where(
            AttendanceSession.section_id == section_id,
            AttendanceSession.academic_year_id == academic_year_id,
            func.extract("month", AttendanceSession.session_date) == month,
            func.extract("year", AttendanceSession.session_date) == year,
        )
        .group_by(AttendanceSession.session_date)
        .order_by(AttendanceSession.session_date.asc())
    )
    if subject_id:
        q = q.where(AttendanceSession.subject_id == subject_id)
    rows = (await db.execute(q)).all()
    days = []
    totals = {"present": 0, "absent": 0, "late": 0, "leave": 0, "total": 0}
    for row in rows:
        present = int(row.present or 0)
        late = int(row.late or 0)
        total = int(row.total or 0)
        pct = round((present + late) * 100.0 / total, 2) if total else 0.0
        status = "holiday" if total == 0 else "present" if pct >= 75 else "leave" if pct >= 50 else "absent"
        days.append(
            {
                "date": row.session_date,
                "present": present,
                "absent": int(row.absent or 0),
                "late": late,
                "leave": int(row.leave or 0),
                "total": total,
                "percentage": pct,
                "status": status,
            }
        )
        totals["present"] += present
        totals["absent"] += int(row.absent or 0)
        totals["late"] += late
        totals["leave"] += int(row.leave or 0)
        totals["total"] += total
    totals["percentage"] = round((totals["present"] + totals["late"]) * 100.0 / totals["total"], 2) if totals["total"] else 0.0
    return {"month": month, "year": year, "summary": totals, "days": days}


def _report_row(row, id_index: bool = False) -> dict:
    if id_index:
        total = row.total or 0
        pct = round(((row.present or 0) + (row.late or 0)) * 100.0 / total, 2) if total else 0.0
        return {
            "subject_id": row.id,
            "subject_name": row.name,
            "present": row.present or 0,
            "absent": row.absent or 0,
            "late": row.late or 0,
            "leave": row.excused or 0,
            "percentage": pct,
            "total": total,
        }
    total = row.total or 0
    pct = round(((row.present or 0) + (row.late or 0)) * 100.0 / total, 2) if total else 0.0
    return {
        "student_id": row.id,
        "roll_number": row.roll_number,
        "full_name": row.full_name,
        "present": row.present or 0,
        "absent": row.absent or 0,
        "late": row.late or 0,
        "leave": row.excused or 0,
        "percentage": pct,
        "total": total,
    }


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


async def _validate_timing_window(db: AsyncSession, timetable_id, session_date: date):
    if not timetable_id:
        return
    if session_date != date.today():
        return
    timetable = (
        await db.execute(select(TeacherTimetable).where(TeacherTimetable.id == timetable_id))
    ).scalar_one_or_none()
    if not timetable:
        return
    now_time = datetime.now().time()
    if now_time < timetable.start_time or now_time > timetable.end_time:
        raise BusinessRuleError("Attendance can be opened only during scheduled class timing")
