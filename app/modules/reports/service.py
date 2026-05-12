from datetime import date
from decimal import Decimal
from io import BytesIO, StringIO
import csv
from sqlalchemy import or_, select, func, case, cast, String
from sqlalchemy.ext.asyncio import AsyncSession
from app.modules.academic.model import AcademicYear, Course, Branch, Class, Section, Subject
from app.modules.attendance.model import AttendanceAuditLog, AttendanceRecord, AttendanceSession, AttendanceStatus, SessionStatus
from app.modules.exams.model import Exam, ExamSubject, ExamWorkflow, Mark
from app.modules.fees.model import FeePayment, FeeStatus, FeeStructure, FeeType, StudentFee
from app.modules.institutions.model import Institution  # noqa: F401 - registers Role.institution relationship
from app.modules.library.model import Book, BookIssue, IssueStatus
from app.modules.logs.model import ActivityLog
from app.modules.notifications.model import NotificationLog, NotificationStatus
from app.modules.organizations.model import Organization  # noqa: F401 - registers Institution.organization relationship
from app.modules.parents import service as parent_portal_service
from app.modules.students.model import Student, StudentAcademicRecord, StudentDocument, StudentStatus
from app.modules.teacher_content.model import Assessment, Assignment, AssignmentSubmission, StudyMaterial
from app.modules.teachers.model import HODLink, Teacher, TeacherClass, TeacherHODSubjectLink, TeacherSubject, TeacherTimetable
from app.modules.users.model import User


def _pdf_bytes(title: str, sections: list[tuple[str, list[list[object]]]]) -> bytes:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=28, leftMargin=28, topMargin=28, bottomMargin=28)
    styles = getSampleStyleSheet()
    story = [Paragraph(title, styles["Title"]), Spacer(1, 12)]
    for heading, rows in sections:
        story.append(Paragraph(heading, styles["Heading2"]))
        if rows:
            table = Table([[str(cell if cell is not None else "") for cell in row] for row in rows], repeatRows=1)
            table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0F2340")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#CBD5E1")),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
            ]))
            story.extend([table, Spacer(1, 12)])
        else:
            story.extend([Paragraph("No records found.", styles["Normal"]), Spacer(1, 12)])
    doc.build(story)
    return buffer.getvalue()


def _csv_bytes(headers: list[str], rows: list[list[object]]) -> bytes:
    stream = StringIO()
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(headers)
    writer.writerows(rows)
    return stream.getvalue().encode("utf-8-sig")


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


async def search_students(
    db: AsyncSession,
    institution_id: str,
    academic_year_id: str | None = None,
    course_id: str | None = None,
    branch_id: str | None = None,
    class_id: str | None = None,
    section_id: str | None = None,
    search: str | None = None,
    limit: int = 25,
) -> list[dict]:
    conditions = [User.institution_id == institution_id, StudentAcademicRecord.exited_at == None]
    if academic_year_id:
        conditions.append(StudentAcademicRecord.academic_year_id == academic_year_id)
    if branch_id:
        conditions.append(StudentAcademicRecord.branch_id == branch_id)
    if class_id:
        conditions.append(Section.class_id == class_id)
    if section_id:
        conditions.append(StudentAcademicRecord.section_id == section_id)
    if course_id:
        conditions.append(Class.course_id == course_id)
    if search:
        text = f"%{search.strip()}%"
        conditions.append(or_(User.full_name.ilike(text), Student.roll_number.ilike(text), User.email.ilike(text)))

    rows = (
        await db.execute(
            select(Student, User, StudentAcademicRecord, Section, Class, Branch, AcademicYear)
            .join(User, User.id == Student.user_id)
            .join(StudentAcademicRecord, StudentAcademicRecord.student_id == Student.id)
            .join(Section, Section.id == StudentAcademicRecord.section_id)
            .join(Class, Class.id == Section.class_id)
            .join(Branch, Branch.id == StudentAcademicRecord.branch_id)
            .join(AcademicYear, AcademicYear.id == StudentAcademicRecord.academic_year_id)
            .where(*conditions)
            .order_by(Student.roll_number.asc(), User.full_name.asc())
            .limit(min(limit, 100))
        )
    ).all()
    return [
        {
            "student_id": str(student.id),
            "roll_number": student.roll_number,
            "full_name": user.full_name,
            "email": user.email,
            "academic_year": year.label,
            "branch": branch.name,
            "class_name": class_.name,
            "section": section.name,
        }
        for student, user, _, section, class_, branch, year in rows
    ]


async def _student_profile(db: AsyncSession, institution_id: str, student_id: str, academic_year_id: str | None = None):
    conditions = [Student.id == student_id, User.institution_id == institution_id, StudentAcademicRecord.exited_at == None]
    if academic_year_id:
        conditions.append(StudentAcademicRecord.academic_year_id == academic_year_id)
    row = (
        await db.execute(
            select(Student, User, StudentAcademicRecord, Section, Class, Branch, AcademicYear)
            .join(User, User.id == Student.user_id)
            .join(StudentAcademicRecord, StudentAcademicRecord.student_id == Student.id)
            .join(Section, Section.id == StudentAcademicRecord.section_id)
            .join(Class, Class.id == Section.class_id)
            .join(Branch, Branch.id == StudentAcademicRecord.branch_id)
            .join(AcademicYear, AcademicYear.id == StudentAcademicRecord.academic_year_id)
            .where(*conditions)
            .order_by(StudentAcademicRecord.enrolled_at.desc())
            .limit(1)
        )
    ).first()
    return row


async def student_complete_report(db: AsyncSession, institution_id: str, student_id: str, academic_year_id: str | None = None) -> dict:
    student_row = (
        await db.execute(
            select(Student, User)
            .join(User, User.id == Student.user_id)
            .where(Student.id == student_id, User.institution_id == institution_id)
        )
    ).first()
    if not student_row:
        return {"found": False, "message": "Student not found in your institution."}

    student, user = student_row
    profile = await _student_profile(db, institution_id, student_id, academic_year_id)
    current_record = profile[2] if profile else None
    current_section = profile[3] if profile else None
    current_class = profile[4] if profile else None
    current_branch = profile[5] if profile else None
    current_year = profile[6] if profile else None
    report_year_id = academic_year_id or (str(current_record.academic_year_id) if current_record else None)

    academic_rows = (
        await db.execute(
            select(StudentAcademicRecord, Section, Class, Branch, Course, AcademicYear)
            .join(Section, Section.id == StudentAcademicRecord.section_id)
            .join(Class, Class.id == Section.class_id)
            .join(Branch, Branch.id == StudentAcademicRecord.branch_id)
            .join(Course, Course.id == Branch.course_id)
            .join(AcademicYear, AcademicYear.id == StudentAcademicRecord.academic_year_id)
            .where(StudentAcademicRecord.student_id == student.id)
            .order_by(StudentAcademicRecord.enrolled_at.desc())
        )
    ).all()
    current_course = next(
        (
            course
            for record, _, _, _, course, _ in academic_rows
            if current_record and record.id == current_record.id
        ),
        academic_rows[0][4] if academic_rows else None,
    )

    attendance = await parent_portal_service.get_attendance_data(db, str(student.id))
    performance = await parent_portal_service.get_performance_data(db, str(student.id))
    fees = await parent_portal_service.get_fees_data(db, str(student.id))
    exams = await parent_portal_service.get_exams_data(db, str(student.id))
    timetable = await parent_portal_service.get_timetable_data(db, str(student.id))

    teacher_rows = []
    if current_record:
        teacher_rows = (
            await db.execute(
                select(Teacher, User, Subject, Section, Class)
                .select_from(TeacherSubject)
                .join(Teacher, Teacher.id == TeacherSubject.teacher_id)
                .join(User, User.id == Teacher.user_id)
                .join(Subject, Subject.id == TeacherSubject.subject_id)
                .join(Section, Section.id == TeacherSubject.section_id)
                .join(Class, Class.id == Section.class_id)
                .where(
                    TeacherSubject.section_id == current_record.section_id,
                    TeacherSubject.academic_year_id == current_record.academic_year_id,
                )
                .order_by(Subject.name.asc(), User.full_name.asc())
            )
        ).all()

    scope_filters = []
    if current_record and current_section:
        scope_filters = [
            StudyMaterial.section_id == current_record.section_id,
            StudyMaterial.academic_year_id == current_record.academic_year_id,
            StudyMaterial.class_id == current_section.class_id,
        ]
    material_rows = []
    if scope_filters:
        material_rows = (
            await db.execute(
                select(StudyMaterial, Subject, Teacher, User)
                .join(Subject, Subject.id == StudyMaterial.subject_id)
                .join(Teacher, Teacher.id == StudyMaterial.teacher_id)
                .join(User, User.id == Teacher.user_id)
                .where(*scope_filters)
                .order_by(StudyMaterial.created_at.desc())
                .limit(50)
            )
        ).all()

    assessment_rows = []
    if current_record and current_section:
        assessment_rows = (
            await db.execute(
                select(Assessment, Subject, Teacher, User)
                .join(Subject, Subject.id == Assessment.subject_id)
                .join(Teacher, Teacher.id == Assessment.teacher_id)
                .join(User, User.id == Teacher.user_id)
                .where(
                    Assessment.section_id == current_record.section_id,
                    Assessment.academic_year_id == current_record.academic_year_id,
                    Assessment.class_id == current_section.class_id,
                )
                .order_by(Assessment.due_date.desc(), Assessment.created_at.desc())
                .limit(50)
            )
        ).all()

    assignment_rows = []
    if current_record and current_section:
        assignment_rows = (
            await db.execute(
                select(Assignment, Subject, Teacher, User, AssignmentSubmission)
                .join(Subject, Subject.id == Assignment.subject_id)
                .join(Teacher, Teacher.id == Assignment.teacher_id)
                .join(User, User.id == Teacher.user_id)
                .outerjoin(
                    AssignmentSubmission,
                    (AssignmentSubmission.assignment_id == Assignment.id) & (AssignmentSubmission.student_id == student.id),
                )
                .where(
                    Assignment.section_id == current_record.section_id,
                    Assignment.academic_year_id == current_record.academic_year_id,
                    Assignment.class_id == current_section.class_id,
                )
                .order_by(Assignment.due_date.desc(), Assignment.created_at.desc())
                .limit(50)
            )
        ).all()

    documents = (
        await db.execute(
            select(StudentDocument)
            .where(StudentDocument.student_id == student.id)
            .order_by(StudentDocument.updated_at.desc(), StudentDocument.created_at.desc())
        )
    ).scalars().all()

    assignment_total = len(assignment_rows)
    assignment_submitted = sum(1 for *_, submission in assignment_rows if submission)
    fee_due = float(fees.get("totalDue") or 0)
    performance_subjects = performance.get("subjects") or []
    average_marks = round(sum(float(item.get("marks") or 0) for item in performance_subjects) / len(performance_subjects), 2) if performance_subjects else 0

    return {
        "found": True,
        "generated_on": date.today().isoformat(),
        "student": {
            "id": str(student.id),
            "user_id": str(user.id),
            "roll_number": student.roll_number,
            "full_name": user.full_name,
            "email": user.email,
            "phone": user.phone,
            "date_of_birth": student.date_of_birth,
            "gender": student.gender,
            "guardian_name": student.guardian_name,
            "guardian_phone": student.guardian_phone,
            "guardian_email": student.guardian_email,
            "admission_date": student.created_at,
            "current_academic_year": current_year.label if current_year else None,
            "course": current_course.name if current_course else None,
            "branch": current_branch.name if current_branch else None,
            "class_name": current_class.name if current_class else None,
            "semester": current_class.semester if current_class else None,
            "section": current_section.name if current_section else None,
            "status": str(current_record.status.value if current_record and hasattr(current_record.status, "value") else current_record.status) if current_record else None,
        },
        "academic_records": [
            {
                "id": str(record.id),
                "academic_year": year.label,
                "course": course.name,
                "branch": branch.name,
                "class_name": class_.name,
                "semester": class_.semester,
                "section": section.name,
                "status": str(record.status.value if hasattr(record.status, "value") else record.status),
                "enrolled_at": record.enrolled_at,
                "exited_at": record.exited_at,
            }
            for record, section, class_, branch, course, year in academic_rows
        ],
        "teachers": [
            {
                "teacher_id": str(teacher.id),
                "teacher_name": teacher_user.full_name,
                "employee_code": teacher.employee_code,
                "designation": teacher.designation,
                "subject": subject.name,
                "subject_code": subject.code,
                "class_name": class_.name,
                "section": section.name,
            }
            for teacher, teacher_user, subject, section, class_ in teacher_rows
        ],
        "attendance": attendance,
        "performance": {**performance, "average_marks": average_marks},
        "fees": fees,
        "exams": exams,
        "timetable": timetable,
        "materials": [
            {
                "id": str(material.id),
                "title": material.title,
                "description": material.description,
                "type": str(material.material_type.value if hasattr(material.material_type, "value") else material.material_type),
                "subject": subject.name,
                "teacher": teacher_user.full_name,
                "created_at": material.created_at,
                "file_name": material.file_name,
                "external_url": material.external_url,
            }
            for material, subject, _, teacher_user in material_rows
        ],
        "assessments": [
            {
                "id": str(item.id),
                "title": item.title,
                "type": str(item.assessment_type.value if hasattr(item.assessment_type, "value") else item.assessment_type),
                "subject": subject.name,
                "teacher": teacher_user.full_name,
                "total_marks": item.total_marks,
                "due_date": item.due_date,
                "instructions": item.instructions,
            }
            for item, subject, _, teacher_user in assessment_rows
        ],
        "assignments": [
            {
                "id": str(item.id),
                "title": item.title,
                "subject": subject.name,
                "teacher": teacher_user.full_name,
                "total_marks": item.total_marks,
                "due_date": item.due_date,
                "submitted": bool(submission),
                "submitted_at": submission.submitted_at if submission else None,
            }
            for item, subject, _, teacher_user, submission in assignment_rows
        ],
        "documents": [
            {
                "id": str(item.id),
                "type": item.document_type,
                "title": item.title,
                "file_name": item.file_name,
                "status": item.status,
                "remarks": item.remarks,
                "updated_at": item.updated_at,
            }
            for item in documents
        ],
        "overall": {
            "attendance_percentage": attendance.get("overall") or 0,
            "cgpa": performance.get("cgpa") or 0,
            "sgpa": performance.get("sgpa") or 0,
            "average_marks": average_marks,
            "pending_fees": fee_due,
            "assignments_total": assignment_total,
            "assignments_submitted": assignment_submitted,
            "assignments_pending": max(assignment_total - assignment_submitted, 0),
            "assessments_total": len(assessment_rows),
            "materials_total": len(material_rows),
            "documents_pending": sum(1 for item in documents if item.status == "pending"),
        },
    }


async def student_complete_report_pdf(db: AsyncSession, institution_id: str, student_id: str, academic_year_id: str | None = None) -> bytes:
    data = await student_complete_report(db, institution_id, student_id, academic_year_id)
    if not data.get("found"):
        return _pdf_bytes("Student Complete Report", [("Student", [["Status"], [data.get("message") or "Student not found."]])])

    student = data.get("student") or {}
    overall = data.get("overall") or {}
    attendance = data.get("attendance") or {}
    performance = data.get("performance") or {}
    fees = data.get("fees") or {}

    return _pdf_bytes(
        f"Student Complete Report - {student.get('full_name') or 'Student'}",
        [
            ("Student & Admission", [
                ["Field", "Value"],
                ["Name", student.get("full_name")],
                ["Roll Number", student.get("roll_number")],
                ["Email", student.get("email")],
                ["Phone", student.get("phone")],
                ["Admission Date", student.get("admission_date")],
                ["Academic Year", student.get("current_academic_year")],
                ["Course / Branch", f"{student.get('course') or '-'} / {student.get('branch') or '-'}"],
                ["Class / Section", f"{student.get('class_name') or '-'} / {student.get('section') or '-'}"],
                ["Guardian", f"{student.get('guardian_name') or '-'} ({student.get('guardian_phone') or '-'})"],
            ]),
            ("Overall Summary", [
                ["Metric", "Value"],
                ["Attendance", f"{overall.get('attendance_percentage') or 0}%"],
                ["CGPA", overall.get("cgpa") or 0],
                ["SGPA", overall.get("sgpa") or 0],
                ["Average Marks", f"{overall.get('average_marks') or 0}%"],
                ["Pending Fees", overall.get("pending_fees") or 0],
                ["Assignments Submitted", f"{overall.get('assignments_submitted') or 0}/{overall.get('assignments_total') or 0}"],
                ["Assessments", overall.get("assessments_total") or 0],
                ["Materials", overall.get("materials_total") or 0],
                ["Pending Documents", overall.get("documents_pending") or 0],
            ]),
            ("Academic Records", [
                ["Year", "Course", "Branch", "Class", "Section", "Status"],
                *[
                    [row.get("academic_year"), row.get("course"), row.get("branch"), row.get("class_name"), row.get("section"), row.get("status")]
                    for row in data.get("academic_records") or []
                ],
            ]),
            ("Teachers", [
                ["Teacher", "Employee Code", "Designation", "Subject", "Class", "Section"],
                *[
                    [row.get("teacher_name"), row.get("employee_code"), row.get("designation"), f"{row.get('subject_code')} - {row.get('subject')}", row.get("class_name"), row.get("section")]
                    for row in data.get("teachers") or []
                ],
            ]),
            ("Attendance", [
                ["Subject", "Attended", "Total", "Percentage"],
                *[
                    [
                        row.get("subject"),
                        row.get("attended"),
                        row.get("total"),
                        f"{round((float(row.get('attended') or 0) / float(row.get('total') or 1)) * 100)}%",
                    ]
                    for row in attendance.get("subjects") or []
                ],
            ]),
            ("Assignments", [
                ["Title", "Subject", "Teacher", "Marks", "Due Date", "Status"],
                *[
                    [row.get("title"), row.get("subject"), row.get("teacher"), row.get("total_marks"), row.get("due_date"), "Submitted" if row.get("submitted") else "Pending"]
                    for row in data.get("assignments") or []
                ],
            ]),
            ("Assessments", [
                ["Title", "Type", "Subject", "Teacher", "Marks", "Due Date"],
                *[
                    [row.get("title"), row.get("type"), row.get("subject"), row.get("teacher"), row.get("total_marks"), row.get("due_date")]
                    for row in data.get("assessments") or []
                ],
            ]),
            ("Materials", [
                ["Title", "Type", "Subject", "Teacher", "Created"],
                *[
                    [row.get("title"), row.get("type"), row.get("subject"), row.get("teacher"), row.get("created_at")]
                    for row in data.get("materials") or []
                ],
            ]),
            ("Fees", [
                ["Fee", "Amount", "Paid", "Balance"],
                *[
                    [row.get("item"), row.get("amount"), row.get("paid"), max(float(row.get("amount") or 0) - float(row.get("paid") or 0), 0)]
                    for row in fees.get("breakdown") or []
                ],
            ]),
            ("Performance", [
                ["Subject", "Marks", "Grade", "Exam"],
                *[
                    [row.get("subject"), f"{row.get('marks')}%", row.get("grade"), row.get("exam")]
                    for row in performance.get("subjects") or []
                ],
            ]),
            ("Documents", [
                ["Document", "Type", "File", "Status", "Updated"],
                *[
                    [row.get("title"), row.get("type"), row.get("file_name"), row.get("status"), row.get("updated_at")]
                    for row in data.get("documents") or []
                ],
            ]),
        ],
    )


async def report_card_pdf(db: AsyncSession, institution_id: str, student_id: str, academic_year_id: str | None = None) -> bytes:
    profile = await _student_profile(db, institution_id, student_id, academic_year_id)
    if not profile:
        return _pdf_bytes("Student Report Card", [("Student", [["Status"], ["Student not found in your institution."]])])
    student, user, record, section, class_, branch, year = profile
    mark_rows = (
        await db.execute(
            select(Exam.name, Subject.code, Subject.name, ExamSubject.max_marks, Mark.marks_obtained, Mark.is_absent)
            .select_from(Mark)
            .join(ExamSubject, ExamSubject.id == Mark.exam_subject_id)
            .join(Exam, Exam.id == ExamSubject.exam_id)
            .join(Subject, Subject.id == ExamSubject.subject_id)
            .where(Mark.student_id == student.id, Exam.academic_year_id == record.academic_year_id)
            .order_by(Exam.name, Subject.code)
        )
    ).all()
    marks_table = [["Exam", "Code", "Subject", "Max", "Obtained", "%", "Result"]]
    for exam, code, subject_name, max_marks, obtained, absent in mark_rows:
        obtained_num = 0 if absent or obtained is None else float(obtained)
        pct = round(obtained_num * 100 / max_marks, 2) if max_marks else 0
        marks_table.append([exam, code, subject_name, max_marks, "Absent" if absent else obtained_num, pct, "Pass" if pct >= 40 and not absent else "Fail"])
    attendance = await _attendance_summary(db, student.id, record.academic_year_id)
    return _pdf_bytes(
        f"Report Card - {user.full_name}",
        [
            ("Student Details", [
                ["Field", "Value"],
                ["Name", user.full_name],
                ["Roll Number", student.roll_number],
                ["Academic Year", year.label],
                ["Branch", branch.name],
                ["Class / Section", f"{class_.name} / {section.name}"],
            ]),
            ("Attendance Summary", [["Present", "Absent", "Late", "Excused", "Percentage"], [attendance["present"], attendance["absent"], attendance["late"], attendance["excused"], f'{attendance["percentage"]}%']]),
            ("Marks", marks_table),
        ],
    )


async def _attendance_summary(db: AsyncSession, student_id, academic_year_id) -> dict:
    row = (
        await db.execute(
            select(
                func.sum(case((cast(AttendanceRecord.status, String) == AttendanceStatus.PRESENT.value, 1), else_=0)).label("present"),
                func.sum(case((cast(AttendanceRecord.status, String) == AttendanceStatus.ABSENT.value, 1), else_=0)).label("absent"),
                func.sum(case((cast(AttendanceRecord.status, String) == AttendanceStatus.LATE.value, 1), else_=0)).label("late"),
                func.sum(case((cast(AttendanceRecord.status, String) == AttendanceStatus.EXCUSED.value, 1), else_=0)).label("excused"),
                func.count(AttendanceRecord.id).label("total"),
            )
            .select_from(AttendanceRecord)
            .join(AttendanceSession, AttendanceSession.id == AttendanceRecord.session_id)
            .where(AttendanceRecord.student_id == student_id, AttendanceSession.academic_year_id == academic_year_id)
        )
    ).first()
    total = int(row.total or 0) if row else 0
    present = int((row.present or 0) + (row.late or 0)) if row else 0
    return {
        "present": int(row.present or 0) if row else 0,
        "absent": int(row.absent or 0) if row else 0,
        "late": int(row.late or 0) if row else 0,
        "excused": int(row.excused or 0) if row else 0,
        "percentage": round(present * 100 / total, 2) if total else 0,
    }


async def attendance_certificate_pdf(db: AsyncSession, institution_id: str, student_id: str, academic_year_id: str | None = None) -> bytes:
    profile = await _student_profile(db, institution_id, student_id, academic_year_id)
    if not profile:
        return _pdf_bytes("Attendance Certificate", [("Student", [["Status"], ["Student not found in your institution."]])])
    student, user, record, section, class_, branch, year = profile
    attendance = await _attendance_summary(db, student.id, record.academic_year_id)
    return _pdf_bytes(
        f"Attendance Certificate - {user.full_name}",
        [("Certificate", [
            ["Field", "Value"],
            ["Student", user.full_name],
            ["Roll Number", student.roll_number],
            ["Academic Year", year.label],
            ["Branch", branch.name],
            ["Class / Section", f"{class_.name} / {section.name}"],
            ["Attendance Percentage", f'{attendance["percentage"]}%'],
            ["Present", attendance["present"]],
            ["Absent", attendance["absent"]],
            ["Generated On", date.today().isoformat()],
        ])],
    )


async def fee_receipt_pdf(db: AsyncSession, institution_id: str, payment_id: str) -> bytes:
    row = (
        await db.execute(
            select(FeePayment, StudentFee, Student, User, FeeStructure, FeeType, Course, AcademicYear)
            .join(StudentFee, StudentFee.id == FeePayment.student_fee_id)
            .join(Student, Student.id == StudentFee.student_id)
            .join(User, User.id == Student.user_id)
            .join(FeeStructure, FeeStructure.id == StudentFee.fee_structure_id)
            .join(FeeType, FeeType.id == FeeStructure.fee_type_id)
            .join(Course, Course.id == FeeStructure.course_id)
            .join(AcademicYear, AcademicYear.id == FeeStructure.academic_year_id)
            .where(FeePayment.id == payment_id, User.institution_id == institution_id)
        )
    ).first()
    if not row:
        return _pdf_bytes("Fee Receipt", [("Payment", [["Status"], ["Payment not found in your institution."]])])
    payment, student_fee, student, user, structure, fee_type, course, year = row
    return _pdf_bytes(
        f"Fee Receipt - {student.roll_number}",
        [("Receipt", [
            ["Field", "Value"],
            ["Receipt ID", payment.id],
            ["Student", user.full_name],
            ["Roll Number", student.roll_number],
            ["Fee Type", fee_type.name],
            ["Course / Year", f"{course.name} / {year.label}"],
            ["Amount Paid", f"Rs. {float(payment.amount):,.2f}"],
            ["Payment Mode", payment.payment_mode],
            ["Transaction Ref", payment.transaction_ref or "-"],
            ["Paid At", payment.paid_at],
            ["Total Due", f"Rs. {float(student_fee.amount_due):,.2f}"],
            ["Total Paid", f"Rs. {float(student_fee.amount_paid):,.2f}"],
            ["Balance", f"Rs. {float(student_fee.amount_due) - float(student_fee.amount_paid):,.2f}"],
        ])],
    )


async def branch_report_rows(db: AsyncSession, institution_id: str, academic_year_id: str | None = None, branch_id: str | None = None) -> list[list[object]]:
    conditions = [User.institution_id == institution_id]
    if academic_year_id:
        conditions.append(StudentAcademicRecord.academic_year_id == academic_year_id)
    if branch_id:
        conditions.append(Branch.id == branch_id)
    rows = (
        await db.execute(
            select(
                Branch.name,
                Class.name,
                Section.name,
                func.count(func.distinct(Student.id)).label("students"),
                func.count(func.distinct(TeacherTimetable.id)).label("slots"),
                func.count(func.distinct(AttendanceSession.id)).label("sessions"),
                func.count(func.distinct(Mark.id)).label("marks"),
            )
            .select_from(StudentAcademicRecord)
            .join(Student, Student.id == StudentAcademicRecord.student_id)
            .join(User, User.id == Student.user_id)
            .join(Branch, Branch.id == StudentAcademicRecord.branch_id)
            .join(Section, Section.id == StudentAcademicRecord.section_id)
            .join(Class, Class.id == Section.class_id)
            .outerjoin(TeacherTimetable, (TeacherTimetable.section_id == Section.id) & (TeacherTimetable.academic_year_id == StudentAcademicRecord.academic_year_id))
            .outerjoin(AttendanceSession, (AttendanceSession.section_id == Section.id) & (AttendanceSession.academic_year_id == StudentAcademicRecord.academic_year_id))
            .outerjoin(Mark, Mark.student_id == Student.id)
            .where(*conditions)
            .group_by(Branch.name, Class.name, Section.name)
            .order_by(Branch.name, Class.name, Section.name)
        )
    ).all()
    return [[branch, class_name, section, students, slots, sessions, marks] for branch, class_name, section, students, slots, sessions, marks in rows]


async def branch_report_csv(db: AsyncSession, institution_id: str, academic_year_id: str | None = None, branch_id: str | None = None) -> bytes:
    rows = await branch_report_rows(db, institution_id, academic_year_id, branch_id)
    return _csv_bytes(["Branch", "Class", "Section", "Students", "Timetable Slots", "Attendance Sessions", "Marks Uploaded"], rows)


async def branch_report_pdf(db: AsyncSession, institution_id: str, academic_year_id: str | None = None, branch_id: str | None = None) -> bytes:
    rows = await branch_report_rows(db, institution_id, academic_year_id, branch_id)
    return _pdf_bytes("HOD / Branch Report", [("Branch Summary", [["Branch", "Class", "Section", "Students", "Slots", "Sessions", "Marks"], *rows])])
