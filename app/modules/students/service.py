from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc, or_, case
from app.modules.students.model import Student, StudentAcademicRecord, StudentStatus, StudentDocument
from app.modules.users.model import User
from app.modules.roles.model import Role, UserRole
from app.modules.students.schema import (
    AcademicRecordCreate,
    PromotionExecuteRequest,
    PromotionPreviewRequest,
    StudentCreate,
    StudentDocumentCreate,
    StudentDocumentUpdate,
    StudentUpdate,
)
from app.core.security import hash_password
from app.core.config import settings
from app.core.exceptions import NotFoundError, ConflictError, BusinessRuleError, ForbiddenError
from app.core.role_context import has_any_role
from app.modules.logs.service import log_activity
from app.modules.parents import service as parent_portal_service
from app.modules.academic.model import AcademicYear, Branch, Class, Course, Section
from app.modules.library.model import Book, BookIssue, IssueStatus
from app.modules.teachers.model import Teacher, TeacherClass, TeacherSubject, TeacherTimetable, HODLink


async def _get_student_role(db: AsyncSession, institution_id) -> Role | None:
    return (
        await db.execute(
            select(Role).where(
                Role.institution_id == institution_id,
                Role.slug == "student",
            )
        )
    ).scalar_one_or_none()


async def create_student(db: AsyncSession, data: StudentCreate) -> Student:
    # Check uniqueness
    ex_user = (await db.execute(select(User).where(User.email == data.email))).scalar_one_or_none()
    if ex_user:
        raise ConflictError("Email already registered")

    ex_roll = (await db.execute(select(Student).where(Student.roll_number == data.roll_number))).scalar_one_or_none()
    if ex_roll:
        raise ConflictError("Roll number already exists")

    # Create user account
    user = User(
        institution_id=data.institution_id,
        email=data.email,
        username=data.username,
        password_hash=hash_password(data.password),
        full_name=data.full_name,
        phone=data.phone,
    )
    db.add(user)
    await db.flush()

    student_role = await _get_student_role(db, data.institution_id)
    if student_role:
        db.add(UserRole(user_id=user.id, role_id=student_role.id))
        await db.flush()

    # Create student profile
    student = Student(
        user_id=user.id,
        roll_number=data.roll_number,
        date_of_birth=data.date_of_birth,
        gender=data.gender,
        guardian_name=data.guardian_name,
        guardian_phone=data.guardian_phone,
        guardian_email=data.guardian_email,
    )
    db.add(student)
    await db.flush()

    # Create initial academic record
    record = StudentAcademicRecord(
        student_id=student.id,
        section_id=data.section_id,
        branch_id=data.branch_id,
        academic_year_id=data.academic_year_id,
        status=StudentStatus.ACTIVE,
    )
    db.add(record)
    await db.flush()
    await db.refresh(student)
    return student


async def list_students(db: AsyncSession, institution_id: str, offset: int, limit: int, search: str | None = None):
    """List students belonging to an institution (via user FK)."""
    q = (
        select(Student)
        .join(User, Student.user_id == User.id)
        .where(User.institution_id == institution_id, User.is_active == True)
    )
    term = (search or "").strip().lower()
    if term:
        like = f"%{term}%"
        starts = f"{term}%"
        q = q.where(
            or_(
                func.lower(User.full_name).like(like),
                func.lower(User.email).like(like),
                func.lower(Student.roll_number).like(like),
                func.lower(Student.guardian_name).like(like),
                func.lower(Student.guardian_email).like(like),
            )
        ).order_by(
            case(
                (func.lower(Student.roll_number) == term, 0),
                (func.lower(User.full_name) == term, 1),
                (func.lower(Student.roll_number).like(starts), 2),
                (func.lower(User.full_name).like(starts), 3),
                else_=4,
            ),
            desc(Student.updated_at),
            desc(Student.created_at),
        )
    else:
        q = q.order_by(desc(Student.updated_at), desc(Student.created_at))
    total = (await db.execute(select(func.count()).select_from(q.subquery()))).scalar()
    result = await db.execute(q.offset(offset).limit(limit))
    return result.scalars().all(), total


async def list_students_for_teacher(
    db: AsyncSession,
    institution_id: str,
    teacher_user_id: str,
    offset: int,
    limit: int,
    search: str | None = None,
):
    teacher = (
        await db.execute(select(Teacher).where(Teacher.user_id == teacher_user_id))
    ).scalar_one_or_none()
    if not teacher:
        return [], 0

    assigned_class_ids = select(TeacherClass.class_id).where(TeacherClass.teacher_id == teacher.id)
    assigned_section_ids = (
        select(TeacherSubject.section_id)
        .where(TeacherSubject.teacher_id == teacher.id)
        .union(
            select(TeacherTimetable.section_id).where(
                TeacherTimetable.teacher_id == teacher.id,
                TeacherTimetable.is_active == True,
            )
        )
    )

    q = (
        select(Student)
        .join(User, Student.user_id == User.id)
        .join(StudentAcademicRecord, StudentAcademicRecord.student_id == Student.id)
        .join(Section, Section.id == StudentAcademicRecord.section_id)
        .where(
            User.institution_id == institution_id,
            User.is_active == True,
            StudentAcademicRecord.exited_at == None,
            StudentAcademicRecord.status == StudentStatus.ACTIVE,
            or_(
                StudentAcademicRecord.section_id.in_(assigned_section_ids),
                Section.class_id.in_(assigned_class_ids),
            ),
        )
        .distinct()
    )
    term = (search or "").strip().lower()
    if term:
        like = f"%{term}%"
        starts = f"{term}%"
        q = q.where(
            or_(
                func.lower(User.full_name).like(like),
                func.lower(User.email).like(like),
                func.lower(Student.roll_number).like(like),
                func.lower(Student.guardian_name).like(like),
                func.lower(Student.guardian_email).like(like),
            )
        ).order_by(
            case(
                (func.lower(Student.roll_number) == term, 0),
                (func.lower(User.full_name) == term, 1),
                (func.lower(Student.roll_number).like(starts), 2),
                (func.lower(User.full_name).like(starts), 3),
                else_=4,
            ),
            desc(Student.updated_at),
            desc(Student.created_at),
        )
    else:
        q = q.order_by(desc(Student.updated_at), desc(Student.created_at))
    total = (await db.execute(select(func.count()).select_from(q.subquery()))).scalar()
    result = await db.execute(q.offset(offset).limit(limit))
    return result.scalars().all(), total


async def list_students_for_hod(
    db: AsyncSession,
    institution_id: str,
    hod_user_id: str,
    offset: int,
    limit: int,
    search: str | None = None,
):
    hod_teacher = (
        await db.execute(select(Teacher).where(Teacher.user_id == hod_user_id))
    ).scalar_one_or_none()
    if not hod_teacher:
        return [], 0

    managed_branch_ids = select(HODLink.branch_id).where(HODLink.hod_teacher_id == hod_teacher.id)
    q = (
        select(Student)
        .join(User, Student.user_id == User.id)
        .join(StudentAcademicRecord, StudentAcademicRecord.student_id == Student.id)
        .where(
            User.institution_id == institution_id,
            User.is_active == True,
            StudentAcademicRecord.exited_at == None,
            StudentAcademicRecord.status == StudentStatus.ACTIVE,
            StudentAcademicRecord.branch_id.in_(managed_branch_ids),
        )
        .distinct()
    )
    term = (search or "").strip().lower()
    if term:
        like = f"%{term}%"
        starts = f"{term}%"
        q = q.where(
            or_(
                func.lower(User.full_name).like(like),
                func.lower(User.email).like(like),
                func.lower(Student.roll_number).like(like),
                func.lower(Student.guardian_name).like(like),
                func.lower(Student.guardian_email).like(like),
            )
        ).order_by(
            case(
                (func.lower(Student.roll_number) == term, 0),
                (func.lower(User.full_name) == term, 1),
                (func.lower(Student.roll_number).like(starts), 2),
                (func.lower(User.full_name).like(starts), 3),
                else_=4,
            ),
            desc(Student.updated_at),
            desc(Student.created_at),
        )
    else:
        q = q.order_by(desc(Student.updated_at), desc(Student.created_at))
    total = (await db.execute(select(func.count()).select_from(q.subquery()))).scalar()
    result = await db.execute(q.offset(offset).limit(limit))
    return result.scalars().all(), total


async def get_student(db: AsyncSession, student_id: str) -> Student:
    result = await db.execute(
        select(Student).where(Student.id == student_id)
    )
    student = result.scalar_one_or_none()
    if not student:
        raise NotFoundError("Student not found")
    return student


async def assert_can_view_student(db: AsyncSession, current_user: dict, student_id: str) -> None:
    if current_user.get("is_superuser") or has_any_role(current_user, {"superadmin", "admin", "principal"}):
        return

    student = await get_student(db, student_id)
    if str(student.user_id) == str(current_user["id"]):
        return

    teacher = (
        await db.execute(select(Teacher).where(Teacher.user_id == current_user["id"]))
    ).scalar_one_or_none()
    if not teacher:
        raise ForbiddenError("You can view only linked student data")

    if has_any_role(current_user, {"hod"}):
        managed_branch_ids = select(HODLink.branch_id).where(HODLink.hod_teacher_id == teacher.id)
        row = (
            await db.execute(
                select(StudentAcademicRecord.id)
                .where(
                    StudentAcademicRecord.student_id == student_id,
                    StudentAcademicRecord.exited_at == None,
                    StudentAcademicRecord.branch_id.in_(managed_branch_ids),
                )
                .limit(1)
            )
        ).first()
        if row:
            return

    assigned_class_ids = select(TeacherClass.class_id).where(TeacherClass.teacher_id == teacher.id)
    assigned_section_ids = (
        select(TeacherSubject.section_id)
        .where(TeacherSubject.teacher_id == teacher.id)
        .union(
            select(TeacherTimetable.section_id).where(
                TeacherTimetable.teacher_id == teacher.id,
                TeacherTimetable.is_active == True,
            )
        )
    )
    row = (
        await db.execute(
            select(StudentAcademicRecord.id)
            .join(Section, Section.id == StudentAcademicRecord.section_id)
            .where(
                StudentAcademicRecord.student_id == student_id,
                StudentAcademicRecord.exited_at == None,
                or_(
                    StudentAcademicRecord.section_id.in_(assigned_section_ids),
                    Section.class_id.in_(assigned_class_ids),
                ),
            )
            .limit(1)
        )
    ).first()
    if row:
        return

    raise ForbiddenError("You can view only linked student data")


async def get_student_by_user_id(db: AsyncSession, user_id: str) -> Student:
    student = (
        await db.execute(select(Student).where(Student.user_id == user_id))
    ).scalar_one_or_none()
    if not student:
        raise NotFoundError("Student profile not found for current user")
    return student


async def get_student_portal(db: AsyncSession, current_user: dict) -> dict:
    student = await get_student_by_user_id(db, current_user["id"])
    user = (
        await db.execute(select(User).where(User.id == student.user_id))
    ).scalar_one()
    student_id = str(student.id)

    attendance = await parent_portal_service.get_attendance_data(db, student_id)
    performance = await parent_portal_service.get_performance_data(db, student_id)
    fees = await parent_portal_service.get_fees_data(db, student_id)
    exams = await parent_portal_service.get_exams_data(db, student_id)
    timetable = await parent_portal_service.get_timetable_data(db, student_id)
    notifications = await parent_portal_service.get_notifications(db, [student_id])
    messages = await parent_portal_service.get_messages(db, [student_id])
    library = await get_student_library_data(db, student_id, user.institution_id)
    current = await _student_academic_snapshot(db, student_id)

    profile = {
        "id": student_id,
        "rollNo": student.roll_number,
        "name": user.full_name,
        "email": user.email,
        "phone": user.phone,
        "avatar": _initials(user.full_name),
        "guardianName": student.guardian_name,
        "guardianPhone": student.guardian_phone,
        "guardianEmail": student.guardian_email,
        "dept": current.get("branch") or "Unassigned",
        "year": current.get("className") or current.get("academicYear") or "",
        "section": current.get("section") or "",
        "semester": current.get("semester") or 0,
        "cgpa": performance["cgpa"],
        "attendance": attendance["overall"],
        "pendingFees": fees["totalDue"],
    }

    return {
        "student": profile,
        "attendance": attendance,
        "performance": performance,
        "fees": fees,
        "exams": exams,
        "timetable": timetable,
        "notifications": notifications,
        "messages": messages,
        "assignments": [],
        "studyMaterials": [],
        "library": library,
    }


async def get_student_library_data(db: AsyncSession, student_id: str, institution_id: str) -> dict:
    books = (
        await db.execute(
            select(Book)
            .where(Book.institution_id == institution_id)
            .order_by(desc(Book.updated_at), desc(Book.created_at), Book.title.asc())
            .limit(100)
        )
    ).scalars().all()

    issues = (
        await db.execute(
            select(BookIssue, Book)
            .join(Book, Book.id == BookIssue.book_id)
            .where(
                BookIssue.student_id == student_id,
                BookIssue.status.in_([IssueStatus.ISSUED, IssueStatus.OVERDUE]),
            )
            .order_by(BookIssue.due_date.asc(), BookIssue.issued_on.desc())
        )
    ).all()

    return {
        "books": [
            {
                "id": str(book.id),
                "title": book.title,
                "author": book.author,
                "publisher": book.publisher,
                "isbn": book.isbn,
                "copies": book.available_copies,
                "available": book.available_copies > 0,
                "updated_at": book.updated_at,
            }
            for book in books
        ],
        "issued": [
            {
                "id": str(issue.id),
                "bookId": str(book.id),
                "title": book.title,
                "author": book.author,
                "issued": issue.issued_on.isoformat() if issue.issued_on else "",
                "due": issue.due_date.isoformat() if issue.due_date else "",
                "fine": _money(issue.fine_amount),
                "status": issue.status.value if hasattr(issue.status, "value") else issue.status,
            }
            for issue, book in issues
        ],
    }


async def get_student_full_profile(db: AsyncSession, student_id: str) -> dict:
    student = await get_student(db, student_id)
    user = (
        await db.execute(select(User).where(User.id == student.user_id))
    ).scalar_one()

    current = await _student_academic_snapshot(db, student_id)
    attendance = await parent_portal_service.get_attendance_data(db, student_id)
    performance = await parent_portal_service.get_performance_data(db, student_id)
    fees = await parent_portal_service.get_fees_data(db, student_id)
    exams = await parent_portal_service.get_exams_data(db, student_id)
    timetable = await parent_portal_service.get_timetable_data(db, student_id)
    behavior = await parent_portal_service.get_behavior_data(db, student_id)
    notifications = await parent_portal_service.get_notifications(db, [student_id])

    academic_records = []
    for record in await list_academic_records(db, student_id):
        row = (
            await db.execute(
                select(
                    Branch.name,
                    Section.name,
                    Class.id,
                    Class.name,
                    AcademicYear.label,
                )
                .select_from(StudentAcademicRecord)
                .join(Section, Section.id == StudentAcademicRecord.section_id)
                .join(Class, Class.id == Section.class_id)
                .join(Branch, Branch.id == StudentAcademicRecord.branch_id)
                .join(AcademicYear, AcademicYear.id == StudentAcademicRecord.academic_year_id)
                .where(StudentAcademicRecord.id == record.id)
            )
        ).first()
        academic_records.append({
            "id": str(record.id),
            "student_id": str(record.student_id),
            "branch_id": str(record.branch_id),
            "branch_name": row[0] if row else None,
            "section_id": str(record.section_id),
            "section_name": row[1] if row else None,
            "class_id": str(row[2]) if row and row[2] else None,
            "class_name": row[3] if row else None,
            "academic_year_id": str(record.academic_year_id),
            "academic_year_label": row[4] if row else None,
            "status": str(record.status.value if hasattr(record.status, "value") else record.status),
            "enrolled_at": record.enrolled_at,
            "exited_at": record.exited_at,
        })

    documents = (
        await db.execute(
            select(StudentDocument)
            .where(StudentDocument.student_id == student_id)
            .order_by(desc(StudentDocument.updated_at), desc(StudentDocument.created_at))
        )
    ).scalars().all()

    return {
        "profile": {
            "id": str(student.id),
            "user_id": str(student.user_id),
            "roll_number": student.roll_number,
            "full_name": user.full_name,
            "email": user.email,
            "phone": user.phone,
            "date_of_birth": student.date_of_birth,
            "gender": student.gender,
            "guardian_name": student.guardian_name,
            "guardian_phone": student.guardian_phone,
            "guardian_email": student.guardian_email,
            "created_at": student.created_at,
            "updated_at": student.updated_at,
            **current,
        },
        "academic_records": academic_records,
        "attendance": attendance,
        "performance": performance,
        "fees": fees,
        "exams": exams,
        "timetable": timetable,
        "behavior": behavior,
        "notifications": notifications,
        "documents": [
            {
                "id": str(item.id),
                "document_type": item.document_type,
                "title": item.title,
                "file_name": item.file_name,
                "file_url": item.file_url,
                "status": item.status,
                "remarks": item.remarks,
                "created_at": item.created_at,
                "updated_at": item.updated_at,
            }
            for item in documents
        ],
    }


def _initials(name: str) -> str:
    parts = [part for part in name.split() if part]
    return "".join(part[0] for part in parts[:2]).upper() or "ST"


async def _student_academic_snapshot(db: AsyncSession, student_id: str) -> dict:
    from app.modules.academic.model import AcademicYear, Branch, Class, Section

    row = (
        await db.execute(
            select(Branch.name, Section.name, Class.name, Class.semester, AcademicYear.label)
            .select_from(StudentAcademicRecord)
            .join(Branch, Branch.id == StudentAcademicRecord.branch_id)
            .join(Section, Section.id == StudentAcademicRecord.section_id)
            .join(Class, Class.id == Section.class_id)
            .join(AcademicYear, AcademicYear.id == StudentAcademicRecord.academic_year_id)
            .where(
                StudentAcademicRecord.student_id == student_id,
                StudentAcademicRecord.exited_at == None,
            )
            .limit(1)
        )
    ).first()
    if not row:
        return {}
    return {
        "branch": row[0],
        "section": row[1],
        "className": row[2],
        "semester": row[3],
        "academicYear": row[4],
    }


async def update_student(db: AsyncSession, student_id: str, data: StudentUpdate) -> Student:
    student = await get_student(db, student_id)
    incoming = data.model_dump(exclude_none=True)

    academic_year_id = incoming.pop("academic_year_id", None)
    branch_id = incoming.pop("branch_id", None)
    section_id = incoming.pop("section_id", None)

    # Update student profile fields
    for k, v in incoming.items():
        if hasattr(student, k):
            setattr(student, k, v)
    # Also update the user's full_name/phone if passed
    user_data = {}
    if "full_name" in incoming:
        user_data["full_name"] = incoming["full_name"]
    if "phone" in incoming:
        user_data["phone"] = incoming["phone"]
    if user_data:
        user = (await db.execute(select(User).where(User.id == student.user_id))).scalar_one()
        for k, v in user_data.items():
            setattr(user, k, v)

    if academic_year_id and branch_id and section_id:
        active = (
            await db.execute(
                select(StudentAcademicRecord).where(
                    StudentAcademicRecord.student_id == student_id,
                    StudentAcademicRecord.exited_at == None,
                )
            )
        ).scalar_one_or_none()
        changed = (
            not active
            or active.academic_year_id != academic_year_id
            or active.branch_id != branch_id
            or active.section_id != section_id
        )
        if changed:
            if active:
                active.exited_at = datetime.now(timezone.utc)
                active.status = StudentStatus.TRANSFERRED
            db.add(
                StudentAcademicRecord(
                    student_id=student.id,
                    section_id=section_id,
                    branch_id=branch_id,
                    academic_year_id=academic_year_id,
                    status=StudentStatus.ACTIVE,
                )
            )
    await db.flush()
    return student


async def delete_student(db: AsyncSession, student_id: str) -> None:
    student = await get_student(db, student_id)
    user = (await db.execute(select(User).where(User.id == student.user_id))).scalar_one()
    user.is_active = False
    active_records = (
        await db.execute(
            select(StudentAcademicRecord).where(
                StudentAcademicRecord.student_id == student.id,
                StudentAcademicRecord.exited_at == None,
            )
        )
    ).scalars().all()
    now = datetime.now(timezone.utc)
    for record in active_records:
        record.exited_at = now
        record.status = StudentStatus.DROPPED
    await db.flush()


async def create_academic_record(
    db: AsyncSession, student_id: str, data: AcademicRecordCreate
) -> StudentAcademicRecord:
    """Close the current active record and open a new one (branch change / new year)."""
    student = await get_student(db, student_id)

    # Close current active record
    active = (
        await db.execute(
            select(StudentAcademicRecord).where(
                StudentAcademicRecord.student_id == student_id,
                StudentAcademicRecord.exited_at == None,
            )
        )
    ).scalar_one_or_none()

    if active:
        active.exited_at = datetime.now(timezone.utc)
        active.status = StudentStatus.TRANSFERRED

    record = StudentAcademicRecord(
        student_id=student_id,
        section_id=data.section_id,
        branch_id=data.branch_id,
        academic_year_id=data.academic_year_id,
        status=StudentStatus.ACTIVE,
    )
    db.add(record)
    await db.flush()
    await db.refresh(record)
    return record


async def _section_context(db: AsyncSession, section_id, academic_year_id, institution_id: str) -> dict:
    row = (
        await db.execute(
            select(Section, Class, Branch, AcademicYear)
            .select_from(Section)
            .join(Class, Class.id == Section.class_id)
            .outerjoin(Branch, Branch.id == Class.branch_id)
            .join(Course, Course.id == Class.course_id)
            .join(AcademicYear, AcademicYear.id == academic_year_id)
            .where(
                Section.id == section_id,
                Course.institution_id == institution_id,
                AcademicYear.institution_id == institution_id,
            )
        )
    ).first()
    if not row:
        raise NotFoundError("Section or academic year not found for this institution")
    section, class_, branch, year = row
    if not branch:
        raise BusinessRuleError("Selected class must be linked to a branch before students can be promoted")
    return {"section": section, "class": class_, "branch": branch, "year": year}


async def _promotion_rows(
    db: AsyncSession,
    institution_id: str,
    from_academic_year_id,
    from_section_id,
    student_ids: list | None = None,
):
    q = (
        select(StudentAcademicRecord, Student, User, Branch.name, Class.name, Section.name, AcademicYear.label)
        .select_from(StudentAcademicRecord)
        .join(Student, Student.id == StudentAcademicRecord.student_id)
        .join(User, User.id == Student.user_id)
        .join(Section, Section.id == StudentAcademicRecord.section_id)
        .join(Class, Class.id == Section.class_id)
        .join(Branch, Branch.id == StudentAcademicRecord.branch_id)
        .join(AcademicYear, AcademicYear.id == StudentAcademicRecord.academic_year_id)
        .where(
            User.institution_id == institution_id,
            User.is_active == True,
            StudentAcademicRecord.academic_year_id == from_academic_year_id,
            StudentAcademicRecord.section_id == from_section_id,
            StudentAcademicRecord.exited_at == None,
            StudentAcademicRecord.status.in_([StudentStatus.ACTIVE, StudentStatus.DETAINED]),
        )
        .order_by(Student.roll_number.asc(), User.full_name.asc())
    )
    if student_ids:
        q = q.where(Student.id.in_(student_ids))
    return (await db.execute(q)).all()


async def preview_promotion(db: AsyncSession, institution_id: str, data: PromotionPreviewRequest) -> dict:
    from_ctx = await _section_context(db, data.from_section_id, data.from_academic_year_id, institution_id)
    to_ctx = await _section_context(db, data.to_section_id, data.to_academic_year_id, institution_id)
    rows = await _promotion_rows(
        db,
        institution_id,
        data.from_academic_year_id,
        data.from_section_id,
        data.student_ids,
    )

    students = []
    for record, student, user, branch_name, class_name, section_name, year_label in rows:
        existing_target = (
            await db.execute(
                select(StudentAcademicRecord.id).where(
                    StudentAcademicRecord.student_id == student.id,
                    StudentAcademicRecord.academic_year_id == data.to_academic_year_id,
                    StudentAcademicRecord.section_id == data.to_section_id,
                    StudentAcademicRecord.exited_at == None,
                )
            )
        ).scalar_one_or_none()
        students.append({
            "student_id": str(student.id),
            "roll_number": student.roll_number,
            "full_name": user.full_name,
            "email": user.email,
            "current_status": record.status.value if hasattr(record.status, "value") else record.status,
            "from_branch_name": branch_name,
            "from_class_name": class_name,
            "from_section_name": section_name,
            "from_academic_year_label": year_label,
            "to_branch_name": to_ctx["branch"].name,
            "to_class_name": to_ctx["class"].name,
            "to_section_name": to_ctx["section"].name,
            "to_academic_year_label": to_ctx["year"].label,
            "can_promote": existing_target is None,
            "warning": "Already active in selected target section/year" if existing_target else None,
        })

    return {
        "from": {
            "academic_year": from_ctx["year"].label,
            "branch": from_ctx["branch"].name,
            "class": from_ctx["class"].name,
            "section": from_ctx["section"].name,
        },
        "to": {
            "academic_year": to_ctx["year"].label,
            "branch": to_ctx["branch"].name,
            "class": to_ctx["class"].name,
            "section": to_ctx["section"].name,
        },
        "total": len(students),
        "students": students,
    }


async def execute_promotion(
    db: AsyncSession,
    institution_id: str,
    data: PromotionExecuteRequest,
    actor_user_id: str | None = None,
) -> dict:
    await _section_context(db, data.from_section_id, data.from_academic_year_id, institution_id)
    default_target = await _section_context(db, data.to_section_id, data.to_academic_year_id, institution_id)
    rows = await _promotion_rows(
        db,
        institution_id,
        data.from_academic_year_id,
        data.from_section_id,
        data.student_ids,
    )
    if not rows:
        raise BusinessRuleError("No active students found in the selected source section")

    decision_map = {str(item.student_id): item for item in (data.decisions or [])}
    counts = {"promoted": 0, "detained": 0, "dropped": 0, "transferred": 0, "graduated": 0, "skipped": 0}
    errors: list[dict] = []
    now = datetime.now(timezone.utc)

    for record, student, user, *_ in rows:
        decision = decision_map.get(str(student.id))
        action = decision.action if decision else "promote"
        try:
            if action == "promote":
                target_section_id = decision.to_section_id if decision and decision.to_section_id else data.to_section_id
                target = default_target if target_section_id == data.to_section_id else await _section_context(
                    db, target_section_id, data.to_academic_year_id, institution_id
                )
                existing_target = (
                    await db.execute(
                        select(StudentAcademicRecord.id).where(
                            StudentAcademicRecord.student_id == student.id,
                            StudentAcademicRecord.academic_year_id == data.to_academic_year_id,
                            StudentAcademicRecord.section_id == target_section_id,
                            StudentAcademicRecord.exited_at == None,
                        )
                    )
                ).scalar_one_or_none()
                if existing_target:
                    counts["skipped"] += 1
                    errors.append({
                        "student_id": str(student.id),
                        "student": user.full_name,
                        "reason": "Student is already active in target section/year",
                    })
                    continue
                record.exited_at = now
                record.status = StudentStatus.TRANSFERRED
                db.add(StudentAcademicRecord(
                    student_id=student.id,
                    section_id=target_section_id,
                    branch_id=target["branch"].id,
                    academic_year_id=data.to_academic_year_id,
                    status=StudentStatus.ACTIVE,
                ))
                counts["promoted"] += 1
            elif action == "detain":
                record.status = StudentStatus.DETAINED
                record.exited_at = None
                counts["detained"] += 1
            elif action == "drop":
                record.status = StudentStatus.DROPPED
                record.exited_at = now
                counts["dropped"] += 1
            elif action == "transfer":
                record.status = StudentStatus.TRANSFERRED
                record.exited_at = now
                counts["transferred"] += 1
            elif action == "graduate":
                record.status = StudentStatus.GRADUATED
                record.exited_at = now
                counts["graduated"] += 1
            else:
                counts["skipped"] += 1
                errors.append({"student_id": str(student.id), "student": user.full_name, "reason": "Invalid action"})
        except Exception as exc:
            counts["skipped"] += 1
            errors.append({"student_id": str(student.id), "student": user.full_name, "reason": str(exc)})

    await db.flush()
    await log_activity(
        db,
        module="students",
        action="student_promotion_execute",
        actor_user_id=actor_user_id,
        institution_id=institution_id,
        entity_type="section",
        entity_id=str(data.from_section_id),
        message="Student promotion workflow executed",
        meta={
            **counts,
            "from_academic_year_id": str(data.from_academic_year_id),
            "from_section_id": str(data.from_section_id),
            "to_academic_year_id": str(data.to_academic_year_id),
            "to_section_id": str(data.to_section_id),
            "errors": errors,
        },
    )
    return {**counts, "errors": errors}


async def list_academic_records(db: AsyncSession, student_id: str):
    student = await get_student(db, student_id)
    result = await db.execute(
        select(StudentAcademicRecord)
        .where(StudentAcademicRecord.student_id == student.id)
        .order_by(StudentAcademicRecord.enrolled_at.desc())
    )
    return result.scalars().all()


async def update_student_status(db: AsyncSession, student_id: str, status: StudentStatus) -> StudentAcademicRecord:
    student = await get_student(db, student_id)
    record = (
        await db.execute(
            select(StudentAcademicRecord)
            .where(
                StudentAcademicRecord.student_id == student.id,
                StudentAcademicRecord.exited_at == None,
            )
            .order_by(StudentAcademicRecord.enrolled_at.desc())
        )
    ).scalar_one_or_none()
    if not record:
        raise NotFoundError("Active academic record not found")
    record.status = status
    if status in (StudentStatus.TRANSFERRED, StudentStatus.GRADUATED, StudentStatus.DROPPED):
        record.exited_at = datetime.now(timezone.utc)
    elif status == StudentStatus.ACTIVE:
        record.exited_at = None
    await db.flush()
    return record


async def list_documents(db: AsyncSession, institution_id: str, offset: int, limit: int):
    q = (
        select(StudentDocument, User.full_name, Student.roll_number)
        .join(Student, Student.id == StudentDocument.student_id)
        .join(User, User.id == Student.user_id)
        .where(User.institution_id == institution_id)
        .order_by(StudentDocument.updated_at.desc(), StudentDocument.created_at.desc())
    )
    total_q = (
        select(func.count(StudentDocument.id))
        .join(Student, Student.id == StudentDocument.student_id)
        .join(User, User.id == Student.user_id)
        .where(User.institution_id == institution_id)
    )
    total = (await db.execute(total_q)).scalar() or 0
    rows = (await db.execute(q.offset(offset).limit(limit))).all()
    return rows, total


async def create_document(db: AsyncSession, data: StudentDocumentCreate) -> StudentDocument:
    await get_student(db, str(data.student_id))
    item = StudentDocument(**data.model_dump())
    db.add(item)
    await db.flush()
    await db.refresh(item)
    return item


async def store_document_file(
    db: AsyncSession,
    *,
    student_id: str,
    document_type: str,
    title: str,
    original_name: str,
    content_type: str | None,
    content: bytes,
    status: str = "pending",
    remarks: str | None = None,
    actor_user_id: str | None = None,
    institution_id: str | None = None,
) -> StudentDocument:
    await get_student(db, student_id)
    allowed_extensions = {".pdf", ".jpg", ".jpeg", ".png", ".webp"}
    suffix = Path(original_name or "").suffix.lower()
    if suffix not in allowed_extensions:
        raise BusinessRuleError("Only PDF and image files are allowed")
    max_bytes = settings.DOCUMENT_MAX_UPLOAD_MB * 1024 * 1024
    if not content or len(content) > max_bytes:
        raise BusinessRuleError(f"Document file must be between 1 byte and {settings.DOCUMENT_MAX_UPLOAD_MB} MB")

    safe_name = "".join(ch if ch.isalnum() or ch in ("-", "_", ".") else "_" for ch in original_name)
    stored_name = f"{uuid4().hex}{suffix}"
    storage_root = Path(settings.DOCUMENT_STORAGE_DIR).resolve()
    student_dir = (storage_root / str(student_id)).resolve()
    if storage_root not in student_dir.parents and student_dir != storage_root:
        raise BusinessRuleError("Invalid document storage path")
    student_dir.mkdir(parents=True, exist_ok=True)
    file_path = student_dir / stored_name
    file_path.write_bytes(content)

    item = StudentDocument(
        student_id=student_id,
        document_type=document_type,
        title=title,
        file_name=safe_name,
        file_url=str(file_path.relative_to(storage_root)),
        status=status,
        remarks=remarks,
    )
    db.add(item)
    await db.flush()
    await db.refresh(item)
    await log_activity(
        db,
        module="students",
        action="document_upload",
        actor_user_id=actor_user_id,
        institution_id=institution_id,
        entity_type="student_document",
        entity_id=str(item.id),
        message="Student document uploaded",
        meta={
            "student_id": str(student_id),
            "document_type": document_type,
            "file_name": safe_name,
            "content_type": content_type,
            "size_bytes": len(content),
        },
    )
    return item


async def get_document_file(db: AsyncSession, document_id: str, institution_id: str) -> tuple[StudentDocument, Path]:
    item = (
        await db.execute(
            select(StudentDocument)
            .join(Student, Student.id == StudentDocument.student_id)
            .join(User, User.id == Student.user_id)
            .where(StudentDocument.id == document_id, User.institution_id == institution_id)
        )
    ).scalar_one_or_none()
    if not item:
        raise NotFoundError("Student document not found")
    if not item.file_url:
        raise NotFoundError("No stored file is attached to this document")
    storage_root = Path(settings.DOCUMENT_STORAGE_DIR).resolve()
    file_path = (storage_root / item.file_url).resolve()
    if storage_root not in file_path.parents:
        raise BusinessRuleError("Invalid document file path")
    if not file_path.exists() or not file_path.is_file():
        raise NotFoundError("Stored document file not found")
    return item, file_path


async def update_document(db: AsyncSession, document_id: str, data: StudentDocumentUpdate) -> StudentDocument:
    item = (
        await db.execute(select(StudentDocument).where(StudentDocument.id == document_id))
    ).scalar_one_or_none()
    if not item:
        raise NotFoundError("Student document not found")
    for key, value in data.model_dump(exclude_none=True).items():
        setattr(item, key, value)
    await db.flush()
    return item


async def delete_document(db: AsyncSession, document_id: str) -> None:
    item = (
        await db.execute(select(StudentDocument).where(StudentDocument.id == document_id))
    ).scalar_one_or_none()
    if not item:
        raise NotFoundError("Student document not found")
    storage_root = Path(settings.DOCUMENT_STORAGE_DIR).resolve()
    if item.file_url:
        file_path = (storage_root / item.file_url).resolve()
        if storage_root in file_path.parents and file_path.exists() and file_path.is_file():
            file_path.unlink()
    await db.delete(item)
    await db.flush()
