from datetime import date
from decimal import Decimal
from sqlalchemy import select, func, case, cast, String
from sqlalchemy.ext.asyncio import AsyncSession
from app.modules.academic.model import AcademicYear, Course, Branch, Class, Section, Subject
from app.modules.attendance.model import AttendanceAuditLog, AttendanceRecord, AttendanceSession, AttendanceStatus, SessionStatus
from app.modules.exams.model import Exam, ExamSubject, ExamWorkflow, Mark
from app.modules.fees.model import FeePayment, FeeStatus, FeeStructure, FeeType, StudentFee
from app.modules.library.model import Book, BookIssue, IssueStatus
from app.modules.logs.model import ActivityLog
from app.modules.notifications.model import NotificationLog, NotificationStatus
from app.modules.students.model import Student, StudentAcademicRecord, StudentDocument, StudentStatus
from app.modules.teachers.model import HODLink, Teacher, TeacherClass, TeacherHODSubjectLink, TeacherSubject, TeacherTimetable
from app.modules.users.model import User


def _num(value) -> float:
    if value is None:
        return 0
    if isinstance(value, Decimal):
        return float(value)
    return value


async def _count(db: AsyncSession, stmt) -> int:
    return int((await db.execute(stmt)).scalar() or 0)


async def build_overview(db: AsyncSession, institution_id: str, academic_year_id: str | None = None) -> dict:
    year = None
    if academic_year_id:
        year = (await db.execute(select(AcademicYear).where(AcademicYear.id == academic_year_id))).scalar_one_or_none()
    if not year:
        year = (
            await db.execute(
                select(AcademicYear)
                .where(AcademicYear.institution_id == institution_id, AcademicYear.is_current == True)
                .limit(1)
            )
        ).scalar_one_or_none()
    year_id = year.id if year else None

    academics = {
        "academic_years": await _count(db, select(func.count(AcademicYear.id)).where(AcademicYear.institution_id == institution_id)),
        "courses": await _count(db, select(func.count(Course.id)).where(Course.institution_id == institution_id)),
        "branches": await _count(db, select(func.count(Branch.id)).join(Course, Course.id == Branch.course_id).where(Course.institution_id == institution_id)),
        "classes": await _count(db, select(func.count(Class.id)).join(Course, Course.id == Class.course_id).where(Course.institution_id == institution_id)),
        "sections": await _count(db, select(func.count(Section.id)).join(Class, Class.id == Section.class_id).join(Course, Course.id == Class.course_id).where(Course.institution_id == institution_id)),
        "subjects": await _count(db, select(func.count(Subject.id)).join(Course, Course.id == Subject.course_id).where(Course.institution_id == institution_id)),
    }

    student_status_rows = (
        await db.execute(
            select(StudentAcademicRecord.status, func.count(StudentAcademicRecord.id))
            .join(Student, Student.id == StudentAcademicRecord.student_id)
            .join(User, User.id == Student.user_id)
            .where(
                User.institution_id == institution_id,
                *(([StudentAcademicRecord.academic_year_id == year_id] if year_id else [])),
            )
            .group_by(StudentAcademicRecord.status)
        )
    ).all()
    student_status = {str(status.value if hasattr(status, "value") else status): int(count or 0) for status, count in student_status_rows}
    students = {
        "total": await _count(db, select(func.count(Student.id)).join(User, User.id == Student.user_id).where(User.institution_id == institution_id)),
        "active": int(student_status.get(StudentStatus.ACTIVE.value, 0)),
        "transferred": int(student_status.get(StudentStatus.TRANSFERRED.value, 0)),
        "detained": int(student_status.get(StudentStatus.DETAINED.value, 0)),
        "graduated": int(student_status.get(StudentStatus.GRADUATED.value, 0)),
        "dropped": int(student_status.get(StudentStatus.DROPPED.value, 0)),
        "guardian_phone_missing": await _count(db, select(func.count(Student.id)).join(User, User.id == Student.user_id).where(User.institution_id == institution_id, Student.guardian_phone == None)),
        "guardian_email_missing": await _count(db, select(func.count(Student.id)).join(User, User.id == Student.user_id).where(User.institution_id == institution_id, Student.guardian_email == None)),
        "documents": await _count(db, select(func.count(StudentDocument.id)).join(Student, Student.id == StudentDocument.student_id).join(User, User.id == Student.user_id).where(User.institution_id == institution_id)),
        "documents_pending": await _count(db, select(func.count(StudentDocument.id)).join(Student, Student.id == StudentDocument.student_id).join(User, User.id == Student.user_id).where(User.institution_id == institution_id, StudentDocument.status == "pending")),
        "documents_verified": await _count(db, select(func.count(StudentDocument.id)).join(Student, Student.id == StudentDocument.student_id).join(User, User.id == Student.user_id).where(User.institution_id == institution_id, StudentDocument.status == "verified")),
    }

    teachers = {
        "total": await _count(db, select(func.count(Teacher.id)).join(User, User.id == Teacher.user_id).where(User.institution_id == institution_id)),
        "class_links": await _count(db, select(func.count(TeacherClass.id)).join(Teacher, Teacher.id == TeacherClass.teacher_id).join(User, User.id == Teacher.user_id).where(User.institution_id == institution_id)),
        "subject_links": await _count(db, select(func.count(TeacherSubject.id)).join(Teacher, Teacher.id == TeacherSubject.teacher_id).join(User, User.id == Teacher.user_id).where(User.institution_id == institution_id)),
        "hod_links": await _count(db, select(func.count(HODLink.id)).where(HODLink.institution_id == institution_id)),
        "teacher_hod_subject_links": await _count(db, select(func.count(TeacherHODSubjectLink.id)).join(HODLink, HODLink.id == TeacherHODSubjectLink.hod_link_id).where(HODLink.institution_id == institution_id)),
        "timetable_slots": await _count(db, select(func.count(TeacherTimetable.id)).join(Teacher, Teacher.id == TeacherTimetable.teacher_id).join(User, User.id == Teacher.user_id).where(User.institution_id == institution_id, TeacherTimetable.is_active == True, *(([TeacherTimetable.academic_year_id == year_id] if year_id else [])))),
    }

    attendance_row = (
        await db.execute(
            select(
                func.count(AttendanceRecord.id).label("total"),
                func.sum(case((cast(AttendanceRecord.status, String) == AttendanceStatus.PRESENT.value, 1), else_=0)).label("present"),
                func.sum(case((cast(AttendanceRecord.status, String) == AttendanceStatus.ABSENT.value, 1), else_=0)).label("absent"),
                func.sum(case((cast(AttendanceRecord.status, String) == AttendanceStatus.LATE.value, 1), else_=0)).label("late"),
                func.sum(case((cast(AttendanceRecord.status, String) == AttendanceStatus.EXCUSED.value, 1), else_=0)).label("excused"),
            )
            .select_from(AttendanceRecord)
            .join(AttendanceSession, AttendanceSession.id == AttendanceRecord.session_id)
            .join(Teacher, Teacher.id == AttendanceSession.teacher_id)
            .join(User, User.id == Teacher.user_id)
            .where(User.institution_id == institution_id, *(([AttendanceSession.academic_year_id == year_id] if year_id else [])))
        )
    ).first()
    total_attendance = int(attendance_row.total or 0) if attendance_row else 0
    present_like = int((attendance_row.present or 0) + (attendance_row.late or 0)) if attendance_row else 0
    attendance = {
        "sessions": await _count(db, select(func.count(AttendanceSession.id)).join(Teacher, Teacher.id == AttendanceSession.teacher_id).join(User, User.id == Teacher.user_id).where(User.institution_id == institution_id, *(([AttendanceSession.academic_year_id == year_id] if year_id else [])))),
        "open_sessions": await _count(db, select(func.count(AttendanceSession.id)).join(Teacher, Teacher.id == AttendanceSession.teacher_id).join(User, User.id == Teacher.user_id).where(User.institution_id == institution_id, cast(AttendanceSession.status, String) == SessionStatus.OPEN.value, *(([AttendanceSession.academic_year_id == year_id] if year_id else [])))),
        "closed_sessions": await _count(db, select(func.count(AttendanceSession.id)).join(Teacher, Teacher.id == AttendanceSession.teacher_id).join(User, User.id == Teacher.user_id).where(User.institution_id == institution_id, cast(AttendanceSession.status, String) == SessionStatus.CLOSED.value, *(([AttendanceSession.academic_year_id == year_id] if year_id else [])))),
        "locked_sessions": await _count(db, select(func.count(AttendanceSession.id)).join(Teacher, Teacher.id == AttendanceSession.teacher_id).join(User, User.id == Teacher.user_id).where(User.institution_id == institution_id, cast(AttendanceSession.status, String) == SessionStatus.LOCKED.value, *(([AttendanceSession.academic_year_id == year_id] if year_id else [])))),
        "records": total_attendance,
        "present": int(attendance_row.present or 0) if attendance_row else 0,
        "absent": int(attendance_row.absent or 0) if attendance_row else 0,
        "late": int(attendance_row.late or 0) if attendance_row else 0,
        "excused": int(attendance_row.excused or 0) if attendance_row else 0,
        "percentage": round(present_like * 100.0 / total_attendance, 2) if total_attendance else 0.0,
        "absent_today": await _count(db, select(func.count(AttendanceRecord.id)).join(AttendanceSession, AttendanceSession.id == AttendanceRecord.session_id).join(Teacher, Teacher.id == AttendanceSession.teacher_id).join(User, User.id == Teacher.user_id).where(User.institution_id == institution_id, AttendanceSession.session_date == date.today(), cast(AttendanceRecord.status, String) == AttendanceStatus.ABSENT.value)),
        "audit_events": await _count(db, select(func.count(AttendanceAuditLog.id)).join(AttendanceSession, AttendanceSession.id == AttendanceAuditLog.session_id).join(Teacher, Teacher.id == AttendanceSession.teacher_id).join(User, User.id == Teacher.user_id).where(User.institution_id == institution_id)),
    }

    fee_row = (
        await db.execute(
            select(
                func.sum(StudentFee.amount_due).label("due"),
                func.sum(StudentFee.amount_paid).label("paid"),
                func.count(StudentFee.id).label("rows"),
                func.sum(case((cast(StudentFee.status, String) == FeeStatus.PAID.value, 1), else_=0)).label("paid_rows"),
                func.sum(case((cast(StudentFee.status, String) == FeeStatus.PARTIAL.value, 1), else_=0)).label("partial_rows"),
                func.sum(case((cast(StudentFee.status, String) == FeeStatus.UNPAID.value, 1), else_=0)).label("unpaid_rows"),
            )
            .select_from(StudentFee)
            .join(Student, Student.id == StudentFee.student_id)
            .join(User, User.id == Student.user_id)
            .where(User.institution_id == institution_id)
        )
    ).first()
    fees = {
        "fee_types": await _count(db, select(func.count(FeeType.id)).where(FeeType.institution_id == institution_id)),
        "fee_structures": await _count(db, select(func.count(FeeStructure.id)).join(FeeType, FeeType.id == FeeStructure.fee_type_id).where(FeeType.institution_id == institution_id, *(([FeeStructure.academic_year_id == year_id] if year_id else [])))),
        "student_fee_rows": int(fee_row.rows or 0) if fee_row else 0,
        "amount_due": round(_num(fee_row.due), 2) if fee_row else 0,
        "amount_paid": round(_num(fee_row.paid), 2) if fee_row else 0,
        "balance": round(_num(fee_row.due) - _num(fee_row.paid), 2) if fee_row else 0,
        "paid_rows": int(fee_row.paid_rows or 0) if fee_row else 0,
        "partial_rows": int(fee_row.partial_rows or 0) if fee_row else 0,
        "unpaid_rows": int(fee_row.unpaid_rows or 0) if fee_row else 0,
        "payments": await _count(db, select(func.count(FeePayment.id)).join(StudentFee, StudentFee.id == FeePayment.student_fee_id).join(Student, Student.id == StudentFee.student_id).join(User, User.id == Student.user_id).where(User.institution_id == institution_id)),
    }

    exam_row = (
        await db.execute(
            select(
                func.count(Mark.id).label("marks"),
                func.sum(case((Mark.is_absent == True, 1), else_=0)).label("absent_marks"),
                func.sum(case((Mark.is_locked == True, 1), else_=0)).label("locked_marks"),
            )
            .select_from(Mark)
            .join(ExamSubject, ExamSubject.id == Mark.exam_subject_id)
            .join(Exam, Exam.id == ExamSubject.exam_id)
            .where(Exam.institution_id == institution_id, *(([Exam.academic_year_id == year_id] if year_id else [])))
        )
    ).first()
    exams = {
        "exams": await _count(db, select(func.count(Exam.id)).where(Exam.institution_id == institution_id, *(([Exam.academic_year_id == year_id] if year_id else [])))),
        "draft": await _count(db, select(func.count(Exam.id)).where(Exam.institution_id == institution_id, cast(Exam.workflow_status, String) == ExamWorkflow.DRAFT.value, *(([Exam.academic_year_id == year_id] if year_id else [])))),
        "submitted": await _count(db, select(func.count(Exam.id)).where(Exam.institution_id == institution_id, cast(Exam.workflow_status, String) == ExamWorkflow.SUBMITTED.value, *(([Exam.academic_year_id == year_id] if year_id else [])))),
        "locked": await _count(db, select(func.count(Exam.id)).where(Exam.institution_id == institution_id, cast(Exam.workflow_status, String) == ExamWorkflow.LOCKED.value, *(([Exam.academic_year_id == year_id] if year_id else [])))),
        "exam_subjects": await _count(db, select(func.count(ExamSubject.id)).join(Exam, Exam.id == ExamSubject.exam_id).where(Exam.institution_id == institution_id, *(([Exam.academic_year_id == year_id] if year_id else [])))),
        "marks_uploaded": int(exam_row.marks or 0) if exam_row else 0,
        "absent_marks": int(exam_row.absent_marks or 0) if exam_row else 0,
        "locked_marks": int(exam_row.locked_marks or 0) if exam_row else 0,
    }

    library = {
        "books": await _count(db, select(func.count(Book.id)).where(Book.institution_id == institution_id)),
        "copies": await _count(db, select(func.coalesce(func.sum(Book.total_copies), 0)).where(Book.institution_id == institution_id)),
        "available_copies": await _count(db, select(func.coalesce(func.sum(Book.available_copies), 0)).where(Book.institution_id == institution_id)),
        "issues": await _count(db, select(func.count(BookIssue.id)).join(Book, Book.id == BookIssue.book_id).where(Book.institution_id == institution_id)),
        "issued": await _count(db, select(func.count(BookIssue.id)).join(Book, Book.id == BookIssue.book_id).where(Book.institution_id == institution_id, cast(BookIssue.status, String) == IssueStatus.ISSUED.value)),
        "returned": await _count(db, select(func.count(BookIssue.id)).join(Book, Book.id == BookIssue.book_id).where(Book.institution_id == institution_id, cast(BookIssue.status, String) == IssueStatus.RETURNED.value)),
        "overdue": await _count(db, select(func.count(BookIssue.id)).join(Book, Book.id == BookIssue.book_id).where(Book.institution_id == institution_id, cast(BookIssue.status, String) == IssueStatus.OVERDUE.value)),
        "fines": round(_num((await db.execute(select(func.coalesce(func.sum(BookIssue.fine_amount), 0)).join(Book, Book.id == BookIssue.book_id).where(Book.institution_id == institution_id))).scalar()), 2),
    }

    notifications = {
        "total": await _count(db, select(func.count(NotificationLog.id)).where(NotificationLog.institution_id == institution_id)),
        "sent": await _count(db, select(func.count(NotificationLog.id)).where(NotificationLog.institution_id == institution_id, cast(NotificationLog.status, String) == NotificationStatus.SENT.value)),
        "failed": await _count(db, select(func.count(NotificationLog.id)).where(NotificationLog.institution_id == institution_id, cast(NotificationLog.status, String) == NotificationStatus.FAILED.value)),
        "skipped": await _count(db, select(func.count(NotificationLog.id)).where(NotificationLog.institution_id == institution_id, cast(NotificationLog.status, String) == NotificationStatus.SKIPPED.value)),
    }

    audit = {
        "activity_logs": await _count(db, select(func.count(ActivityLog.id)).where(ActivityLog.institution_id == institution_id)),
        "attendance_audit_logs": attendance["audit_events"],
        "notification_logs": notifications["total"],
    }

    recent_events = []
    for row in (
        await db.execute(
            select(ActivityLog.module, ActivityLog.action, ActivityLog.message, ActivityLog.created_at)
            .where(ActivityLog.institution_id == institution_id)
            .order_by(ActivityLog.created_at.desc())
            .limit(8)
        )
    ).all():
        recent_events.append({"module": row.module, "action": row.action, "message": row.message, "created_at": row.created_at})
    for row in (
        await db.execute(
            select(NotificationLog.channel, NotificationLog.status, NotificationLog.subject, NotificationLog.created_at)
            .where(NotificationLog.institution_id == institution_id)
            .order_by(NotificationLog.created_at.desc())
            .limit(8)
        )
    ).all():
        recent_events.append({"module": "notifications", "action": str(row.status.value if hasattr(row.status, "value") else row.status), "message": f"{row.channel}: {row.subject or 'notification'}", "created_at": row.created_at})
    recent_events = sorted(recent_events, key=lambda item: item["created_at"], reverse=True)[:12]

    coverage = [
        {"module": "Academics", "status": "covered", "details": "Years, courses, branches, classes, sections, subjects"},
        {"module": "Students", "status": "covered", "details": "Admissions, records, guardians, documents, lifecycle status"},
        {"module": "Teachers/HOD", "status": "covered", "details": "Profiles, HOD links, subject links, timetable workload"},
        {"module": "Attendance", "status": "covered", "details": "Sessions, records, absent totals, audit events"},
        {"module": "Fees", "status": "covered", "details": "Demand, paid, balance, status buckets, payments"},
        {"module": "Exams", "status": "covered", "details": "Workflow, subjects, marks, absent/locked marks"},
        {"module": "Library", "status": "covered", "details": "Books, copies, issues, returns, overdue, fines"},
        {"module": "Notifications", "status": "covered", "details": "Email/SMS delivery logs and failures"},
        {"module": "Audit", "status": "covered", "details": "Activity logs and attendance audit trail"},
    ]

    return {
        "academic_year_id": str(year.id) if year else None,
        "academic_year_label": year.label if year else None,
        "generated_on": date.today().isoformat(),
        "academics": academics,
        "students": students,
        "teachers": teachers,
        "attendance": attendance,
        "fees": fees,
        "exams": exams,
        "library": library,
        "notifications": notifications,
        "audit": audit,
        "recent_events": recent_events,
        "coverage": coverage,
    }
