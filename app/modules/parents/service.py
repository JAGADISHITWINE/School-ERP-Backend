from __future__ import annotations

from collections import defaultdict
from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import and_, desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ForbiddenError, NotFoundError
from app.modules.academic.model import AcademicYear, Branch, Class, Course, Section, Subject
from app.modules.attendance.model import AttendanceRecord, AttendanceSession, AttendanceStatus
from app.modules.exams.model import Exam, ExamSubject, Mark
from app.modules.fees.model import FeePayment, FeeStructure, FeeType, StudentFee
from app.modules.notifications.model import NotificationLog
from app.modules.roles.model import Role, UserRole
from app.modules.students.model import Student, StudentAcademicRecord
from app.modules.teachers.model import Teacher, TeacherTimetable, TimetableDay
from app.modules.users.model import User


def _money(value: Any) -> float:
    if value is None:
        return 0.0
    if isinstance(value, Decimal):
        return float(value)
    return float(value)


def _grade(percent: float) -> str:
    if percent >= 90:
        return "A+"
    if percent >= 80:
        return "A"
    if percent >= 70:
        return "B+"
    if percent >= 60:
        return "B"
    if percent >= 50:
        return "C"
    if percent >= 40:
        return "D"
    return "F"


def _status_value(value: Any) -> str:
    return getattr(value, "value", value)


def _initials(name: str) -> str:
    parts = [p for p in name.split() if p]
    return "".join(p[0] for p in parts[:2]).upper() or "ST"


async def _assert_parent_role(db: AsyncSession, current_user: dict) -> None:
    if current_user.get("is_superuser"):
        return
    row = (
        await db.execute(
            select(Role.slug)
            .join(UserRole, UserRole.role_id == Role.id)
            .where(UserRole.user_id == current_user["id"])
        )
    ).scalars().all()
    if "parent" not in {str(slug).lower() for slug in row}:
        raise ForbiddenError("Parent portal access requires parent role")


async def _current_parent_user(db: AsyncSession, current_user: dict) -> User:
    user = (
        await db.execute(select(User).where(User.id == current_user["id"]))
    ).scalar_one_or_none()
    if not user:
        raise NotFoundError("Parent user not found")
    return user


async def _student_ids_for_parent(db: AsyncSession, current_user: dict) -> list[str]:
    await _assert_parent_role(db, current_user)
    user = await _current_parent_user(db, current_user)
    rows = (
        await db.execute(
            select(Student.id)
            .join(User, User.id == Student.user_id)
            .where(
                User.institution_id == user.institution_id,
                func.lower(Student.guardian_email) == user.email.lower(),
            )
            .order_by(Student.roll_number)
        )
    ).scalars().all()
    return [str(student_id) for student_id in rows]


async def assert_parent_can_access_student(db: AsyncSession, current_user: dict, student_id: str) -> None:
    ids = await _student_ids_for_parent(db, current_user)
    if student_id not in ids:
        raise ForbiddenError("You can access only your linked children")


async def get_parent_children(db: AsyncSession, current_user: dict) -> list[dict]:
    await _assert_parent_role(db, current_user)
    user = await _current_parent_user(db, current_user)
    rows = (
        await db.execute(
            select(Student, User, StudentAcademicRecord, Section, Class, Branch, Course, AcademicYear)
            .join(User, User.id == Student.user_id)
            .outerjoin(
                StudentAcademicRecord,
                and_(
                    StudentAcademicRecord.student_id == Student.id,
                    StudentAcademicRecord.exited_at.is_(None),
                ),
            )
            .outerjoin(Section, Section.id == StudentAcademicRecord.section_id)
            .outerjoin(Class, Class.id == Section.class_id)
            .outerjoin(Branch, Branch.id == StudentAcademicRecord.branch_id)
            .outerjoin(Course, Course.id == Branch.course_id)
            .outerjoin(AcademicYear, AcademicYear.id == StudentAcademicRecord.academic_year_id)
            .where(
                User.institution_id == user.institution_id,
                func.lower(Student.guardian_email) == user.email.lower(),
            )
            .order_by(Student.roll_number)
        )
    ).all()

    children = []
    for student, student_user, record, section, class_, branch, course, year in rows:
        attendance = await get_attendance_data(db, str(student.id))
        performance = await get_performance_data(db, str(student.id))
        fees = await get_fees_data(db, str(student.id))
        children.append(
            {
                "id": str(student.id),
                "name": student_user.full_name,
                "rollNo": student.roll_number,
                "program": course.name if course else "College Program",
                "branch": branch.name if branch else "Unassigned",
                "semester": class_.semester if class_ and class_.semester else 0,
                "year": class_.name if class_ else (year.label if year else ""),
                "section": section.name if section else "",
                "avatar": _initials(student_user.full_name),
                "attendance": attendance["overall"],
                "cgpa": performance["cgpa"],
                "pendingFees": fees["totalDue"],
                "guardianName": student.guardian_name,
                "guardianPhone": student.guardian_phone,
                "guardianEmail": student.guardian_email,
                "status": _status_value(record.status) if record else None,
            }
        )
    return children


async def get_parent_portal(db: AsyncSession, current_user: dict) -> dict:
    user = await _current_parent_user(db, current_user)
    children = await get_parent_children(db, current_user)
    data_by_child = {}
    for child in children:
        student_id = child["id"]
        data_by_child[student_id] = {
            "attendance": await get_attendance_data(db, student_id),
            "performance": await get_performance_data(db, student_id),
            "fees": await get_fees_data(db, student_id),
            "exams": await get_exams_data(db, student_id),
            "timetable": await get_timetable_data(db, student_id),
            "behavior": await get_behavior_data(db, student_id),
        }
    return {
        "parentName": user.full_name,
        "parentEmail": user.email,
        "children": children,
        "dataByChild": data_by_child,
        "notifications": await get_notifications(db, [child["id"] for child in children]),
        "messages": await get_messages(db, [child["id"] for child in children]),
        "meetingRequests": [],
    }


async def get_attendance_data(db: AsyncSession, student_id: str) -> dict:
    rows = (
        await db.execute(
            select(AttendanceRecord, AttendanceSession, Subject)
            .join(AttendanceSession, AttendanceSession.id == AttendanceRecord.session_id)
            .join(Subject, Subject.id == AttendanceSession.subject_id)
            .where(AttendanceRecord.student_id == student_id)
            .order_by(AttendanceSession.session_date)
        )
    ).all()

    total = len(rows)
    present_count = sum(
        1
        for record, _, _ in rows
        if record.status in (AttendanceStatus.PRESENT, AttendanceStatus.LATE, AttendanceStatus.EXCUSED)
    )
    overall = round((present_count / total) * 100) if total else 0

    monthly_bucket: dict[str, list[bool]] = defaultdict(list)
    subject_bucket: dict[str, dict[str, int]] = defaultdict(lambda: {"attended": 0, "total": 0})
    recent_rows = rows[-30:]
    recent = []
    for record, session, subject in rows:
        attended = record.status in (AttendanceStatus.PRESENT, AttendanceStatus.LATE, AttendanceStatus.EXCUSED)
        key = session.session_date.strftime("%b")
        monthly_bucket[key].append(attended)
        subject_bucket[subject.name]["total"] += 1
        if attended:
            subject_bucket[subject.name]["attended"] += 1

    for idx, (record, session, _) in enumerate(recent_rows, start=1):
        status = record.status
        recent.append(
            {
                "day": session.session_date.day if session.session_date else idx,
                "date": session.session_date.isoformat() if session.session_date else None,
                "status": "P" if status == AttendanceStatus.PRESENT else "A" if status == AttendanceStatus.ABSENT else "L",
            }
        )

    monthly = [
        {"month": month, "percent": round((sum(values) / len(values)) * 100) if values else 0}
        for month, values in list(monthly_bucket.items())[-6:]
    ]
    subjects = [
        {"subject": subject, "attended": values["attended"], "total": values["total"]}
        for subject, values in subject_bucket.items()
    ]
    return {"overall": overall, "monthly": monthly, "subjects": subjects, "recent": recent}


async def get_performance_data(db: AsyncSession, student_id: str) -> dict:
    rows = (
        await db.execute(
            select(Mark, ExamSubject, Exam, Subject)
            .join(ExamSubject, ExamSubject.id == Mark.exam_subject_id)
            .join(Exam, Exam.id == ExamSubject.exam_id)
            .join(Subject, Subject.id == ExamSubject.subject_id)
            .where(Mark.student_id == student_id)
            .order_by(Exam.created_at, Subject.name)
        )
    ).all()
    subjects = []
    trend_bucket: dict[str, list[float]] = defaultdict(list)
    for mark, exam_subject, exam, subject in rows:
        max_marks = exam_subject.max_marks or 100
        obtained = 0 if mark.is_absent or mark.marks_obtained is None else _money(mark.marks_obtained)
        percent = round((obtained / max_marks) * 100, 2) if max_marks else 0
        subjects.append(
            {
                "subject": subject.name,
                "marks": round(percent),
                "grade": "AB" if mark.is_absent else _grade(percent),
                "credits": subject.credits or 0,
                "exam": exam.name,
            }
        )
        sem = f"Sem {subject.semester or ''}".strip()
        trend_bucket[sem].append(percent)

    avg = round(sum(s["marks"] for s in subjects) / len(subjects), 2) if subjects else 0
    cgpa = round(avg / 10, 2)
    trend = [
        {"sem": sem, "sgpa": round((sum(values) / len(values)) / 10, 2)}
        for sem, values in trend_bucket.items()
    ] or [{"sem": "Current", "sgpa": cgpa}]
    return {"cgpa": cgpa, "sgpa": trend[-1]["sgpa"], "subjects": subjects, "trend": trend}


async def get_fees_data(db: AsyncSession, student_id: str) -> dict:
    rows = (
        await db.execute(
            select(StudentFee, FeeStructure, FeeType)
            .join(FeeStructure, FeeStructure.id == StudentFee.fee_structure_id)
            .join(FeeType, FeeType.id == FeeStructure.fee_type_id)
            .where(StudentFee.student_id == student_id)
            .order_by(FeeType.name)
        )
    ).all()
    fee_ids = [student_fee.id for student_fee, _, _ in rows]
    payment_rows = []
    if fee_ids:
        payment_rows = (
            await db.execute(
                select(FeePayment)
                .where(FeePayment.student_fee_id.in_(fee_ids))
                .order_by(desc(FeePayment.paid_at))
            )
        ).scalars().all()

    breakdown = []
    for student_fee, _, fee_type in rows:
        amount = _money(student_fee.amount_due)
        paid = _money(student_fee.amount_paid)
        breakdown.append({"item": fee_type.name, "amount": amount, "paid": paid})

    history = [
        {
            "id": payment.transaction_ref or str(payment.id)[:8].upper(),
            "date": payment.paid_at.date().isoformat() if payment.paid_at else "",
            "amount": _money(payment.amount),
            "mode": payment.payment_mode.upper(),
            "status": "Paid",
        }
        for payment in payment_rows
    ]
    total_due = sum(max(0, item["amount"] - item["paid"]) for item in breakdown)
    return {"totalDue": total_due, "breakdown": breakdown, "history": history}


async def get_exams_data(db: AsyncSession, student_id: str) -> dict:
    performance = await get_performance_data(db, student_id)
    record = await _active_record(db, student_id)
    upcoming = []
    if record:
        section = (
            await db.execute(select(Section).where(Section.id == record.section_id))
        ).scalar_one_or_none()
        rows = (
            await db.execute(
                select(ExamSubject, Exam, Subject)
                .join(Exam, Exam.id == ExamSubject.exam_id)
                .join(Subject, Subject.id == ExamSubject.subject_id)
                .where(
                    Exam.academic_year_id == record.academic_year_id,
                    or_(Subject.branch_id == record.branch_id, Subject.branch_id.is_(None)),
                    or_(Subject.class_id == section.class_id if section else None, Subject.class_id.is_(None)),
                    ExamSubject.exam_date >= date.today(),
                )
                .order_by(ExamSubject.exam_date)
            )
        ).all()
        upcoming = [
            {
                "id": str(exam_subject.id),
                "name": f"{exam.name} - {subject.name}",
                "date": exam_subject.exam_date.isoformat() if exam_subject.exam_date else "",
                "time": "10:00 AM",
                "venue": "Exam Hall",
                "status": "Upcoming",
            }
            for exam_subject, exam, subject in rows
        ]

    results = [
        {"subject": item["subject"], "max": 100, "obtained": item["marks"], "grade": item["grade"]}
        for item in performance["subjects"]
    ]
    return {"upcoming": upcoming, "results": results, "sgpaTrend": performance["trend"]}


async def _active_record(db: AsyncSession, student_id: str) -> StudentAcademicRecord | None:
    return (
        await db.execute(
            select(StudentAcademicRecord)
            .where(StudentAcademicRecord.student_id == student_id, StudentAcademicRecord.exited_at.is_(None))
            .order_by(desc(StudentAcademicRecord.enrolled_at))
            .limit(1)
        )
    ).scalar_one_or_none()


async def get_timetable_data(db: AsyncSession, student_id: str) -> dict:
    record = await _active_record(db, student_id)
    days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    result = {day: [] for day in days}
    if not record:
        return result
    rows = (
        await db.execute(
            select(TeacherTimetable, Subject, Teacher, User)
            .join(Subject, Subject.id == TeacherTimetable.subject_id)
            .join(Teacher, Teacher.id == TeacherTimetable.teacher_id)
            .join(User, User.id == Teacher.user_id)
            .where(TeacherTimetable.section_id == record.section_id, TeacherTimetable.is_active == True)
            .order_by(TeacherTimetable.day_of_week, TeacherTimetable.start_time)
        )
    ).all()
    day_map = {
        TimetableDay.MONDAY: "Mon",
        TimetableDay.TUESDAY: "Tue",
        TimetableDay.WEDNESDAY: "Wed",
        TimetableDay.THURSDAY: "Thu",
        TimetableDay.FRIDAY: "Fri",
        TimetableDay.SATURDAY: "Sat",
        TimetableDay.SUNDAY: "Sun",
    }
    for slot, subject, teacher, user in rows:
        day = day_map.get(slot.day_of_week, "Mon")
        result[day].append(
            {
                "id": str(slot.id),
                "start": slot.start_time.strftime("%H:%M"),
                "end": slot.end_time.strftime("%H:%M"),
                "subject": subject.name,
                "faculty": user.full_name,
                "room": slot.room_no or "Room",
                "type": "Lab" if "lab" in subject.name.lower() else "Lecture",
            }
        )
    return result


async def get_notifications(db: AsyncSession, student_ids: list[str]) -> list[dict]:
    if not student_ids:
        return []
    rows = (
        await db.execute(
            select(NotificationLog)
            .where(NotificationLog.student_id.in_(student_ids))
            .order_by(desc(NotificationLog.created_at))
            .limit(20)
        )
    ).scalars().all()
    return [
        {
            "id": str(row.id),
            "title": row.subject or (row.body or "Notification")[:80],
            "type": "danger" if row.channel.value == "sms" and row.status.value == "failed" else "info",
            "time": row.created_at.strftime("%d %b %Y") if row.created_at else "",
        }
        for row in rows
    ]


async def get_messages(db: AsyncSession, student_ids: list[str]) -> list[dict]:
    notifications = await get_notifications(db, student_ids)
    messages = []
    for item in notifications:
        messages.append(
            {
                "id": item["id"],
                "from": "College Office",
                "role": "ERP Notification",
                "subject": item["title"],
                "preview": item["title"],
                "body": item["title"],
                "time": item["time"],
                "unread": False,
                "thread": [
                    {
                        "id": f"{item['id']}-1",
                        "author": "teacher",
                        "name": "College Office",
                        "body": item["title"],
                        "time": item["time"],
                    }
                ],
            }
        )
    return messages


async def get_behavior_data(db: AsyncSession, student_id: str) -> dict:
    attendance = await get_attendance_data(db, student_id)
    score = min(100, max(0, attendance["overall"]))
    remarks = []
    if attendance["overall"] and attendance["overall"] < 75:
        remarks.append(
            {
                "id": f"attendance-{student_id}",
                "type": "feedback",
                "title": "Attendance needs attention",
                "by": "Academic Office",
                "role": "Attendance",
                "date": date.today().strftime("%d %b %Y"),
                "body": "Attendance is below the recommended minimum. Please connect with the class teacher.",
            }
        )
    return {"score": score, "remarks": remarks}
