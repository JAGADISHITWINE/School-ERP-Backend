from datetime import date, datetime, timezone
from pathlib import Path
from uuid import uuid4

from sqlalchemy import and_, desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import BusinessRuleError, ConflictError, ForbiddenError, NotFoundError, ValidationError
from app.modules.academic.model import AcademicYear, Branch, Class, Section, Subject
from app.modules.roles.model import Role, UserRole
from app.modules.students.model import Student, StudentAcademicRecord, StudentStatus
from app.modules.teacher_content.model import (
    Assessment,
    Assignment,
    AssignmentSubmission,
    StudyMaterial,
)
from app.modules.teacher_content.schema import AssessmentCreate, AssignmentCreate, MaterialCreate
from app.modules.teachers.model import HODLink, Teacher, TeacherHODSubjectLink, TeacherSubject, TeacherTimetable
from app.modules.users.model import User

TEACHER_LINK_MESSAGE = "Teacher is not linked to the selected class/section/subject."
CONTENT_MAX_UPLOAD_MB = 25


async def user_has_role(db: AsyncSession, user_id: str, *roles: str) -> bool:
    wanted = {role.lower() for role in roles}
    row = (
        await db.execute(
            select(Role.slug, Role.name)
            .join(UserRole, UserRole.role_id == Role.id)
            .where(UserRole.user_id == user_id)
        )
    ).all()
    return any((slug or "").lower() in wanted or (name or "").lower() in wanted for slug, name in row)


async def resolve_teacher(db: AsyncSession, user_id: str) -> Teacher:
    teacher = (
        await db.execute(select(Teacher).where(Teacher.user_id == user_id))
    ).scalar_one_or_none()
    if not teacher:
        raise NotFoundError("Teacher profile not found for current user")
    return teacher


async def resolve_student(db: AsyncSession, user_id: str) -> Student:
    student = (
        await db.execute(select(Student).where(Student.user_id == user_id))
    ).scalar_one_or_none()
    if not student:
        raise NotFoundError("Student profile not found for current user")
    return student


async def assigned_dropdowns(db: AsyncSession, user_id: str) -> dict:
    teacher = await resolve_teacher(db, user_id)
    scope = await _teacher_scope_rows(db, str(teacher.id))
    return {
        "academic_years": _unique(scope, "academic_year_id", "academic_year_label"),
        "branches": _unique(scope, "branch_id", "branch_name"),
        "classes": _unique(scope, "class_id", "class_name", extra_keys=("branch_id", "branch_name")),
        "sections": _unique(scope, "section_id", "section_name", extra_keys=("class_id", "class_name")),
        "subjects": _unique(scope, "subject_id", "subject_name", extra_keys=("class_id", "section_id")),
    }


async def create_material(
    db: AsyncSession,
    user_id: str,
    data: MaterialCreate,
    *,
    original_name: str | None = None,
    content_type: str | None = None,
    content: bytes | None = None,
) -> StudyMaterial:
    teacher = await resolve_teacher(db, user_id)
    await validate_teacher_assignment(db, teacher, data)
    file_name, file_url = await _store_optional_file(
        "materials", original_name=original_name, content_type=content_type, content=content
    )
    if not file_url and not data.external_url:
        raise ValidationError("Provide a file upload or URL")
    item = StudyMaterial(
        teacher_id=teacher.id,
        **data.model_dump(exclude={"external_url"}),
        file_name=file_name,
        file_url=file_url,
        external_url=data.external_url,
    )
    db.add(item)
    await db.flush()
    await db.refresh(item)
    return item


async def create_assessment(
    db: AsyncSession,
    user_id: str,
    data: AssessmentCreate,
    *,
    original_name: str | None = None,
    content_type: str | None = None,
    content: bytes | None = None,
) -> Assessment:
    teacher = await resolve_teacher(db, user_id)
    await validate_teacher_assignment(db, teacher, data)
    _validate_due_date(data.due_date)
    duplicate = (
        await db.execute(
            select(Assessment.id).where(
                func.lower(Assessment.title) == data.title.strip().lower(),
                Assessment.subject_id == data.subject_id,
                Assessment.class_id == data.class_id,
                Assessment.section_id == data.section_id,
                Assessment.due_date == data.due_date,
            )
        )
    ).first()
    if duplicate:
        raise ConflictError("Assessment title already exists for the same subject/class/section/date")
    attachment_name, attachment_url = await _store_optional_file(
        "assessments", original_name=original_name, content_type=content_type, content=content
    )
    item = Assessment(
        teacher_id=teacher.id,
        **data.model_dump(),
        attachment_name=attachment_name,
        attachment_url=attachment_url,
    )
    db.add(item)
    await db.flush()
    await db.refresh(item)
    return item


async def create_assignment(
    db: AsyncSession,
    user_id: str,
    data: AssignmentCreate,
    *,
    original_name: str | None = None,
    content_type: str | None = None,
    content: bytes | None = None,
) -> Assignment:
    teacher = await resolve_teacher(db, user_id)
    await validate_teacher_assignment(db, teacher, data)
    _validate_due_date(data.due_date)
    attachment_name, attachment_url = await _store_optional_file(
        "assignments", original_name=original_name, content_type=content_type, content=content
    )
    item = Assignment(
        teacher_id=teacher.id,
        **data.model_dump(),
        attachment_name=attachment_name,
        attachment_url=attachment_url,
    )
    db.add(item)
    await db.flush()
    await db.refresh(item)
    return item


async def list_teacher_materials(db: AsyncSession, user_id: str, filters: dict, offset: int, limit: int):
    teacher = await resolve_teacher(db, user_id)
    q = _content_select(StudyMaterial).where(StudyMaterial.teacher_id == teacher.id)
    q = _apply_filters(q, StudyMaterial, filters)
    return await _paged(db, q.order_by(desc(StudyMaterial.created_at)), offset, limit)


async def list_teacher_assessments(db: AsyncSession, user_id: str, filters: dict, offset: int, limit: int):
    teacher = await resolve_teacher(db, user_id)
    q = _content_select(Assessment).where(Assessment.teacher_id == teacher.id)
    q = _apply_filters(q, Assessment, filters)
    return await _paged(db, q.order_by(desc(Assessment.due_date), desc(Assessment.created_at)), offset, limit)


async def list_teacher_assignments(db: AsyncSession, user_id: str, filters: dict, offset: int, limit: int):
    teacher = await resolve_teacher(db, user_id)
    q = (
        _content_select(Assignment)
        .add_columns(func.count(AssignmentSubmission.id).label("submission_count"))
        .outerjoin(AssignmentSubmission, AssignmentSubmission.assignment_id == Assignment.id)
        .where(Assignment.teacher_id == teacher.id)
        .group_by(Assignment.id, AcademicYear.label, Branch.name, Class.name, Section.name, Subject.name)
    )
    q = _apply_filters(q, Assignment, filters)
    return await _paged(db, q.order_by(desc(Assignment.due_date), desc(Assignment.created_at)), offset, limit)


async def list_student_materials(db: AsyncSession, user_id: str, filters: dict, offset: int, limit: int):
    record = await _active_student_record(db, user_id)
    q = _content_select(StudyMaterial).where(
        StudyMaterial.academic_year_id == record.academic_year_id,
        StudyMaterial.branch_id == record.branch_id,
        StudyMaterial.section_id == record.section_id,
    )
    q = _apply_filters(q, StudyMaterial, filters)
    return await _paged(db, q.order_by(desc(StudyMaterial.created_at)), offset, limit)


async def list_student_assessments(db: AsyncSession, user_id: str, filters: dict, offset: int, limit: int):
    record = await _active_student_record(db, user_id)
    q = _content_select(Assessment).where(
        Assessment.academic_year_id == record.academic_year_id,
        Assessment.branch_id == record.branch_id,
        Assessment.section_id == record.section_id,
    )
    q = _apply_filters(q, Assessment, filters)
    return await _paged(db, q.order_by(desc(Assessment.due_date), desc(Assessment.created_at)), offset, limit)


async def list_student_assignments(db: AsyncSession, user_id: str, filters: dict, offset: int, limit: int):
    student = await resolve_student(db, user_id)
    record = await _active_student_record(db, user_id)
    submitted = (
        select(AssignmentSubmission.id)
        .where(
            AssignmentSubmission.assignment_id == Assignment.id,
            AssignmentSubmission.student_id == student.id,
        )
        .exists()
    )
    q = (
        _content_select(Assignment)
        .add_columns(func.count(AssignmentSubmission.id).label("submission_count"), submitted.label("submitted"))
        .outerjoin(AssignmentSubmission, AssignmentSubmission.assignment_id == Assignment.id)
        .where(
            Assignment.academic_year_id == record.academic_year_id,
            Assignment.branch_id == record.branch_id,
            Assignment.section_id == record.section_id,
        )
        .group_by(Assignment.id, AcademicYear.label, Branch.name, Class.name, Section.name, Subject.name)
    )
    q = _apply_filters(q, Assignment, filters)
    return await _paged(db, q.order_by(desc(Assignment.due_date), desc(Assignment.created_at)), offset, limit)


async def submit_assignment(
    db: AsyncSession,
    user_id: str,
    assignment_id: str,
    remarks: str | None,
    *,
    original_name: str | None = None,
    content_type: str | None = None,
    content: bytes | None = None,
) -> AssignmentSubmission:
    student = await resolve_student(db, user_id)
    record = await _active_student_record(db, user_id)
    assignment = (
        await db.execute(select(Assignment).where(Assignment.id == assignment_id))
    ).scalar_one_or_none()
    if not assignment:
        raise NotFoundError("Assignment not found")
    if (
        assignment.academic_year_id != record.academic_year_id
        or assignment.branch_id != record.branch_id
        or assignment.section_id != record.section_id
    ):
        raise ForbiddenError("This assignment is not assigned to your class/section")
    existing = (
        await db.execute(
            select(AssignmentSubmission).where(
                AssignmentSubmission.assignment_id == assignment.id,
                AssignmentSubmission.student_id == student.id,
            )
        )
    ).scalar_one_or_none()
    if existing:
        raise ConflictError("Assignment already submitted")
    attachment_name, attachment_url = await _store_optional_file(
        "submissions", original_name=original_name, content_type=content_type, content=content
    )
    if not attachment_url and not (remarks or "").strip():
        raise ValidationError("Provide a file or remarks for the submission")
    item = AssignmentSubmission(
        assignment_id=assignment.id,
        student_id=student.id,
        remarks=remarks,
        attachment_name=attachment_name,
        attachment_url=attachment_url,
        submitted_at=datetime.now(timezone.utc),
    )
    db.add(item)
    await db.flush()
    await db.refresh(item)
    return item


async def list_assignment_submissions(db: AsyncSession, user_id: str, assignment_id: str):
    teacher = await resolve_teacher(db, user_id)
    assignment = (
        await db.execute(
            select(Assignment).where(Assignment.id == assignment_id, Assignment.teacher_id == teacher.id)
        )
    ).scalar_one_or_none()
    if not assignment:
        raise NotFoundError("Assignment not found")
    rows = (
        await db.execute(
            select(AssignmentSubmission, User.full_name, Student.roll_number)
            .join(Student, Student.id == AssignmentSubmission.student_id)
            .join(User, User.id == Student.user_id)
            .where(AssignmentSubmission.assignment_id == assignment.id)
            .order_by(AssignmentSubmission.submitted_at.desc())
        )
    ).all()
    return rows


async def get_content_file(db: AsyncSession, table: str, item_id: str, user_id: str, institution_id: str) -> tuple[str, Path]:
    model, name_attr, url_attr = {
        "materials": (StudyMaterial, "file_name", "file_url"),
        "assessments": (Assessment, "attachment_name", "attachment_url"),
        "assignments": (Assignment, "attachment_name", "attachment_url"),
        "submissions": (AssignmentSubmission, "attachment_name", "attachment_url"),
    }[table]
    item = (await db.execute(select(model).where(model.id == item_id))).scalar_one_or_none()
    if not item:
        raise NotFoundError("File not found")
    await _ensure_file_access(db, item, table, user_id, institution_id)
    relative = getattr(item, url_attr)
    if not relative:
        raise NotFoundError("No stored file is attached")
    storage_root = Path(settings.DOCUMENT_STORAGE_DIR).resolve().parent / "teacher-content"
    file_path = (storage_root / relative).resolve()
    if storage_root.resolve() not in file_path.parents:
        raise BusinessRuleError("Invalid content file path")
    if not file_path.exists() or not file_path.is_file():
        raise NotFoundError("Stored file not found")
    return getattr(item, name_attr) or file_path.name, file_path


async def validate_teacher_assignment(db: AsyncSession, teacher: Teacher, data) -> None:
    row = (
        await db.execute(
            select(Class, Section, Subject, AcademicYear)
            .join(Section, Section.class_id == Class.id)
            .join(Subject, Subject.class_id == Class.id)
            .join(AcademicYear, AcademicYear.id == data.academic_year_id)
            .where(
                Class.id == data.class_id,
                Section.id == data.section_id,
                Subject.id == data.subject_id,
                or_(Class.branch_id == data.branch_id, Subject.branch_id == data.branch_id),
            )
        )
    ).first()
    if not row:
        raise ValidationError("Selected branch/class/section/subject is invalid")
    class_obj, _section, subject, _year = row
    if class_obj.academic_year_id and class_obj.academic_year_id != data.academic_year_id:
        raise ValidationError("Class does not belong to the selected academic year")
    if subject.academic_year_id and subject.academic_year_id != data.academic_year_id:
        raise ValidationError("Subject does not belong to the selected academic year")

    exact_subject = (
        await db.execute(
            select(TeacherSubject.id).where(
                TeacherSubject.teacher_id == teacher.id,
                TeacherSubject.subject_id == data.subject_id,
                TeacherSubject.section_id == data.section_id,
                TeacherSubject.academic_year_id == data.academic_year_id,
            )
        )
    ).first()
    exact_timetable = (
        await db.execute(
            select(TeacherTimetable.id).where(
                TeacherTimetable.teacher_id == teacher.id,
                TeacherTimetable.class_id == data.class_id,
                TeacherTimetable.section_id == data.section_id,
                TeacherTimetable.subject_id == data.subject_id,
                TeacherTimetable.academic_year_id == data.academic_year_id,
                TeacherTimetable.is_active == True,
            )
        )
    ).first()
    hod_subject = (
        await db.execute(
            select(TeacherHODSubjectLink.id)
            .join(HODLink, HODLink.id == TeacherHODSubjectLink.hod_link_id)
            .where(
                TeacherHODSubjectLink.teacher_id == teacher.id,
                TeacherHODSubjectLink.subject_id == data.subject_id,
                HODLink.branch_id == data.branch_id,
            )
            .limit(1)
        )
    ).first()
    if not exact_subject and not exact_timetable and not hod_subject:
        raise ValidationError(TEACHER_LINK_MESSAGE)


def _validate_due_date(value: date) -> None:
    if value < date.today():
        raise ValidationError("Due date should not be in the past")


async def _store_optional_file(
    bucket: str,
    *,
    original_name: str | None,
    content_type: str | None,
    content: bytes | None,
) -> tuple[str | None, str | None]:
    if not content:
        return None, None
    allowed_extensions = {".pdf", ".doc", ".docx", ".ppt", ".pptx", ".jpg", ".jpeg", ".png", ".webp", ".mp4", ".mov", ".txt"}
    suffix = Path(original_name or "").suffix.lower()
    if suffix not in allowed_extensions:
        raise BusinessRuleError("Unsupported file type")
    max_bytes = CONTENT_MAX_UPLOAD_MB * 1024 * 1024
    if len(content) > max_bytes:
        raise BusinessRuleError(f"File size must be {CONTENT_MAX_UPLOAD_MB} MB or less")
    safe_name = "".join(ch if ch.isalnum() or ch in ("-", "_", ".") else "_" for ch in (original_name or "attachment"))
    storage_root = (Path(settings.DOCUMENT_STORAGE_DIR).resolve().parent / "teacher-content").resolve()
    bucket_dir = (storage_root / bucket).resolve()
    if storage_root not in bucket_dir.parents and bucket_dir != storage_root:
        raise BusinessRuleError("Invalid content storage path")
    bucket_dir.mkdir(parents=True, exist_ok=True)
    stored_name = f"{uuid4().hex}{suffix}"
    (bucket_dir / stored_name).write_bytes(content)
    return safe_name, str(Path(bucket) / stored_name)


async def _teacher_scope_rows(db: AsyncSession, teacher_id: str) -> list[dict]:
    subject_rows = (
        await db.execute(
            select(
                AcademicYear.id.label("academic_year_id"),
                AcademicYear.label.label("academic_year_label"),
                Branch.id.label("branch_id"),
                Branch.name.label("branch_name"),
                Class.id.label("class_id"),
                Class.name.label("class_name"),
                Section.id.label("section_id"),
                Section.name.label("section_name"),
                Subject.id.label("subject_id"),
                Subject.name.label("subject_name"),
            )
            .select_from(TeacherSubject)
            .join(Section, Section.id == TeacherSubject.section_id)
            .join(Class, Class.id == Section.class_id)
            .join(Branch, Branch.id == Class.branch_id)
            .join(Subject, Subject.id == TeacherSubject.subject_id)
            .join(AcademicYear, AcademicYear.id == TeacherSubject.academic_year_id)
            .where(TeacherSubject.teacher_id == teacher_id)
        )
    ).mappings().all()
    timetable_rows = (
        await db.execute(
            select(
                AcademicYear.id.label("academic_year_id"),
                AcademicYear.label.label("academic_year_label"),
                Branch.id.label("branch_id"),
                Branch.name.label("branch_name"),
                Class.id.label("class_id"),
                Class.name.label("class_name"),
                Section.id.label("section_id"),
                Section.name.label("section_name"),
                Subject.id.label("subject_id"),
                Subject.name.label("subject_name"),
            )
            .select_from(TeacherTimetable)
            .join(Class, Class.id == TeacherTimetable.class_id)
            .join(Branch, Branch.id == Class.branch_id)
            .join(Section, Section.id == TeacherTimetable.section_id)
            .join(Subject, Subject.id == TeacherTimetable.subject_id)
            .join(AcademicYear, AcademicYear.id == TeacherTimetable.academic_year_id)
            .where(TeacherTimetable.teacher_id == teacher_id, TeacherTimetable.is_active == True)
        )
    ).mappings().all()
    return [dict(row) for row in [*subject_rows, *timetable_rows]]


def _unique(rows: list[dict], id_key: str, label_key: str, extra_keys: tuple[str, ...] = ()) -> list[dict]:
    seen = set()
    items = []
    for row in rows:
        value = row.get(id_key)
        if not value or value in seen:
            continue
        seen.add(value)
        item = {"id": str(value), "name": row.get(label_key), "label": row.get(label_key)}
        for key in extra_keys:
            item[key] = str(row[key]) if row.get(key) is not None else None
        items.append(item)
    return items


def _content_select(model):
    return (
        select(
            model,
            AcademicYear.label.label("academic_year_label"),
            Branch.name.label("branch_name"),
            Class.name.label("class_name"),
            Section.name.label("section_name"),
            Subject.name.label("subject_name"),
        )
        .join(AcademicYear, AcademicYear.id == model.academic_year_id)
        .join(Branch, Branch.id == model.branch_id)
        .join(Class, Class.id == model.class_id)
        .join(Section, Section.id == model.section_id)
        .join(Subject, Subject.id == model.subject_id)
    )


def _apply_filters(q, model, filters: dict):
    for key in ("academic_year_id", "class_id", "section_id", "subject_id"):
        if filters.get(key):
            q = q.where(getattr(model, key) == filters[key])
    if filters.get("from_date") and hasattr(model, "due_date"):
        q = q.where(model.due_date >= filters["from_date"])
    if filters.get("to_date") and hasattr(model, "due_date"):
        q = q.where(model.due_date <= filters["to_date"])
    return q


async def _paged(db: AsyncSession, q, offset: int, limit: int):
    total = (await db.execute(select(func.count()).select_from(q.subquery()))).scalar() or 0
    rows = (await db.execute(q.offset(offset).limit(limit))).all()
    return rows, total


async def _active_student_record(db: AsyncSession, user_id: str) -> StudentAcademicRecord:
    student = await resolve_student(db, user_id)
    record = (
        await db.execute(
            select(StudentAcademicRecord)
            .where(
                StudentAcademicRecord.student_id == student.id,
                StudentAcademicRecord.exited_at == None,
                StudentAcademicRecord.status == StudentStatus.ACTIVE,
            )
            .order_by(StudentAcademicRecord.enrolled_at.desc())
        )
    ).scalar_one_or_none()
    if not record:
        raise NotFoundError("Active academic record not found for current student")
    return record


async def _ensure_file_access(db: AsyncSession, item, table: str, user_id: str, institution_id: str) -> None:
    assignment = None
    if table == "submissions":
        assignment = (
            await db.execute(select(Assignment).where(Assignment.id == item.assignment_id))
        ).scalar_one_or_none()
        if not assignment:
            raise NotFoundError("Assignment not found")
    if await user_has_role(db, user_id, "teacher"):
        teacher = await resolve_teacher(db, user_id)
        owner_id = assignment.teacher_id if assignment else item.teacher_id
        if owner_id == teacher.id:
            return
    if await user_has_role(db, user_id, "student"):
        record = await _active_student_record(db, user_id)
        content_item = assignment if assignment else item
        if (
            content_item.academic_year_id == record.academic_year_id
            and content_item.branch_id == record.branch_id
            and content_item.section_id == record.section_id
        ):
            return
    raise ForbiddenError("You do not have access to this file")
