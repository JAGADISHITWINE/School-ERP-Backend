from datetime import date, time
from io import BytesIO, StringIO
import csv
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, literal, or_
from app.modules.teachers.model import Teacher, TeacherSubject, TeacherClass, TeacherTimetable, TimetableDay
from app.modules.users.model import User
from app.modules.roles.model import Role, UserRole
from app.modules.academic.model import Class, Branch, Course, AcademicYear, Section, Subject
from app.modules.attendance.model import AttendanceSession
from app.modules.teachers.schema import (
    TeacherCreate,
    SubjectAssignRequest,
    TeacherClassAssignRequest,
    TeacherTimetableCreate,
    TeacherTimetableUpdate,
)
from app.core.security import hash_password
from app.core.exceptions import NotFoundError, ConflictError, ValidationError, BusinessRuleError


async def create_teacher(
    db: AsyncSession, data: TeacherCreate, actor_institution_id: str | None = None
) -> Teacher:
    ex_code = (
        await db.execute(select(Teacher).where(Teacher.employee_code == data.employee_code))
    ).scalar_one_or_none()
    if ex_code:
        raise ConflictError("Employee code already in use")

    if data.user_id:
        user = (
            await db.execute(select(User).where(User.id == data.user_id))
        ).scalar_one_or_none()
        if not user:
            raise NotFoundError("User not found")
        if actor_institution_id and str(user.institution_id) != actor_institution_id:
            raise ValidationError("Selected user does not belong to your institution")

        existing_teacher = (
            await db.execute(select(Teacher).where(Teacher.user_id == user.id))
        ).scalar_one_or_none()
        if existing_teacher:
            raise ConflictError("Teacher profile already exists for this user")

        has_teacher_role = await _user_has_teacher_role(db, str(user.id))
        if not has_teacher_role:
            raise ValidationError("Selected user does not have the Teacher role")
    else:
        institution_id = actor_institution_id or str(data.institution_id)
        ex = (await db.execute(select(User).where(User.email == data.email))).scalar_one_or_none()
        if ex:
            raise ConflictError("Email already registered")
        ex2 = (
            await db.execute(select(User).where(User.username == data.username))
        ).scalar_one_or_none()
        if ex2:
            raise ConflictError("Username already taken")

        user = User(
            institution_id=institution_id,
            email=data.email,
            username=data.username,
            password_hash=hash_password(data.password),
            full_name=data.full_name,
            phone=data.phone,
        )
        db.add(user)
        await db.flush()

        teacher_role = await _get_teacher_role(db, institution_id)
        if teacher_role:
            db.add(UserRole(user_id=user.id, role_id=teacher_role.id))
            await db.flush()

    teacher = Teacher(
        user_id=user.id,
        employee_code=data.employee_code,
        designation=data.designation,
        joined_at=data.joined_at,
    )
    db.add(teacher)
    await db.flush()
    await db.refresh(teacher)
    return teacher


async def list_teachers(db: AsyncSession, institution_id: str, offset: int, limit: int):
    q = (
        select(Teacher)
        .join(User, Teacher.user_id == User.id)
        .where(User.institution_id == institution_id)
    )
    total = (await db.execute(select(func.count()).select_from(q.subquery()))).scalar()
    result = await db.execute(q.offset(offset).limit(limit))
    return result.scalars().all(), total


async def get_teacher(db: AsyncSession, teacher_id: str) -> Teacher:
    obj = (await db.execute(select(Teacher).where(Teacher.id == teacher_id))).scalar_one_or_none()
    if not obj:
        raise NotFoundError("Teacher not found")
    return obj


async def list_teacher_candidates(db: AsyncSession, institution_id: str):
    teacher_user_ids = (
        select(Teacher.user_id)
        .subquery()
    )
    rows = (
        await db.execute(
            select(User)
            .join(UserRole, UserRole.user_id == User.id)
            .join(Role, Role.id == UserRole.role_id)
            .where(
                User.institution_id == institution_id,
                _teacher_role_filter(),
                ~User.id.in_(select(teacher_user_ids.c.user_id)),
            )
            .order_by(User.full_name.asc())
        )
    ).scalars().all()
    return rows


async def assign_subject(db: AsyncSession, teacher_id: str, data: SubjectAssignRequest) -> TeacherSubject:
    await get_teacher(db, teacher_id)
    ts = TeacherSubject(
        teacher_id=teacher_id,
        subject_id=data.subject_id,
        section_id=data.section_id,
        academic_year_id=data.academic_year_id,
    )
    db.add(ts)
    await db.flush()
    await db.refresh(ts)
    return ts


async def list_teacher_classes(db: AsyncSession, teacher_id: str) -> list[dict]:
    await get_teacher(db, teacher_id)

    rows = (
        await db.execute(
            select(
                TeacherClass.id,
                Class.id.label("class_id"),
                Class.name.label("class_name"),
                Class.semester,
                Branch.id.label("branch_id"),
                Branch.name.label("branch_name"),
                Class.academic_year_id,
                AcademicYear.label.label("academic_year_label"),
            )
            .join(Class, Class.id == TeacherClass.class_id)
            .join(Branch, Branch.id == Class.branch_id)
            .outerjoin(AcademicYear, AcademicYear.id == Class.academic_year_id)
            .where(TeacherClass.teacher_id == teacher_id)
            .order_by(Branch.name.asc(), Class.semester.asc(), Class.name.asc())
        )
    ).mappings().all()
    return [dict(row) for row in rows]


async def list_teacher_timetable(
    db: AsyncSession,
    teacher_id: str,
    day_of_week: TimetableDay | None = None,
    session_date: date | None = None,
) -> list[dict]:
    await get_teacher(db, teacher_id)

    q = (
        select(
            TeacherTimetable.id,
            TeacherTimetable.teacher_id,
            TeacherTimetable.class_id,
            Class.name.label("class_name"),
            TeacherTimetable.section_id,
            Section.name.label("section_name"),
            TeacherTimetable.subject_id,
            Subject.name.label("subject_name"),
            Branch.id.label("branch_id"),
            Branch.name.label("branch_name"),
            TeacherTimetable.academic_year_id,
            AcademicYear.label.label("academic_year_label"),
            TeacherTimetable.day_of_week,
            TeacherTimetable.start_time,
            TeacherTimetable.end_time,
            TeacherTimetable.room_no,
            TeacherTimetable.version_no,
            TeacherTimetable.is_active,
        )
        .join(Class, Class.id == TeacherTimetable.class_id)
        .join(Section, Section.id == TeacherTimetable.section_id)
        .join(Subject, Subject.id == TeacherTimetable.subject_id)
        .join(Branch, Branch.id == Class.branch_id)
        .join(AcademicYear, AcademicYear.id == TeacherTimetable.academic_year_id)
        .where(TeacherTimetable.teacher_id == teacher_id)
    )
    q = q.where(TeacherTimetable.is_active == True)

    if session_date:
        q = q.add_columns(
            AttendanceSession.id.label("session_id"),
            AttendanceSession.status.label("session_status"),
            AttendanceSession.session_date,
        ).outerjoin(
            AttendanceSession,
            (AttendanceSession.timetable_id == TeacherTimetable.id)
            & (AttendanceSession.session_date == session_date),
        )
    else:
        q = q.add_columns(
            literal(None).label("session_id"),
            literal(None).label("session_status"),
            literal(None).label("session_date"),
        )

    target_day = day_of_week or (_date_to_day(session_date) if session_date else None)
    if target_day:
        q = q.where(TeacherTimetable.day_of_week == target_day)

    rows = (
        await db.execute(
            q.order_by(
                TeacherTimetable.day_of_week.asc(),
                TeacherTimetable.start_time.asc(),
                Class.name.asc(),
                Section.name.asc(),
            )
        )
    ).mappings().all()
    return [dict(row) for row in rows]


async def assign_class(
    db: AsyncSession, teacher_id: str, data: TeacherClassAssignRequest
) -> TeacherClass:
    teacher = await get_teacher(db, teacher_id)
    class_obj = (
        await db.execute(
            select(Class, Course.institution_id)
            .join(Branch, Branch.id == Class.branch_id)
            .join(Course, Course.id == Branch.course_id)
            .where(Class.id == data.class_id)
        )
    ).first()
    if not class_obj:
        raise NotFoundError("Class not found")

    class_row, class_institution_id = class_obj
    user = (
        await db.execute(select(User).where(User.id == teacher.user_id))
    ).scalar_one()
    if class_institution_id != user.institution_id:
        raise ValidationError("Class does not belong to the teacher's institution")

    existing = (
        await db.execute(
            select(TeacherClass).where(
                TeacherClass.teacher_id == teacher.id,
                TeacherClass.class_id == data.class_id,
            )
        )
    ).scalar_one_or_none()
    if existing:
        raise ConflictError("Class already assigned to this teacher")

    teacher_class = TeacherClass(teacher_id=teacher.id, class_id=class_row.id)
    db.add(teacher_class)
    await db.flush()
    await db.refresh(teacher_class)
    return teacher_class


async def create_timetable_entry(
    db: AsyncSession, teacher_id: str, data: TeacherTimetableCreate
) -> TeacherTimetable:
    teacher = await get_teacher(db, teacher_id)
    class_obj, section_obj, subject_obj = await _validate_timetable_refs(
        db,
        teacher,
        data.class_id,
        data.section_id,
        data.subject_id,
        data.academic_year_id,
    )

    _validate_time_range(data.start_time, data.end_time)
    await _ensure_timetable_slot_available(
        db,
        teacher.id,
        data.section_id,
        data.day_of_week,
        data.start_time,
        data.end_time,
        exclude_id=None,
    )
    await _ensure_teacher_subject_link(
        db,
        teacher.id,
        data.subject_id,
        data.section_id,
        data.academic_year_id,
    )

    entry = TeacherTimetable(
        teacher_id=teacher.id,
        class_id=class_obj.id,
        section_id=section_obj.id,
        subject_id=subject_obj.id,
        academic_year_id=data.academic_year_id,
        day_of_week=data.day_of_week,
        start_time=data.start_time,
        end_time=data.end_time,
        room_no=data.room_no,
        version_no=data.version_no,
        is_active=data.is_active,
    )
    db.add(entry)
    await db.flush()
    await db.refresh(entry)
    return entry


async def update_timetable_entry(
    db: AsyncSession, entry_id: str, data: TeacherTimetableUpdate
) -> TeacherTimetable:
    entry = await _get_timetable_entry(db, entry_id)
    teacher = await get_teacher(db, str(entry.teacher_id))
    incoming = data.model_dump(exclude_unset=True)

    class_id = incoming.get("class_id", entry.class_id)
    section_id = incoming.get("section_id", entry.section_id)
    subject_id = incoming.get("subject_id", entry.subject_id)
    academic_year_id = incoming.get("academic_year_id", entry.academic_year_id)
    day_of_week = incoming.get("day_of_week", entry.day_of_week)
    start_time = incoming.get("start_time", entry.start_time)
    end_time = incoming.get("end_time", entry.end_time)

    await _validate_timetable_refs(
        db,
        teacher,
        class_id,
        section_id,
        subject_id,
        academic_year_id,
    )
    _validate_time_range(start_time, end_time)
    await _ensure_timetable_slot_available(
        db,
        teacher.id,
        section_id,
        day_of_week,
        start_time,
        end_time,
        exclude_id=entry.id,
    )
    await _ensure_teacher_subject_link(
        db,
        teacher.id,
        subject_id,
        section_id,
        academic_year_id,
    )

    for key, value in incoming.items():
        setattr(entry, key, value)

    await db.flush()
    await db.refresh(entry)
    return entry


async def delete_timetable_entry(db: AsyncSession, entry_id: str) -> None:
    entry = await _get_timetable_entry(db, entry_id)
    active_session = (
        await db.execute(
            select(AttendanceSession.id).where(
                AttendanceSession.teacher_id == entry.teacher_id,
                AttendanceSession.section_id == entry.section_id,
                AttendanceSession.subject_id == entry.subject_id,
                AttendanceSession.academic_year_id == entry.academic_year_id,
            )
        )
    ).first()
    if active_session:
        raise BusinessRuleError("Cannot delete timetable entry with linked attendance sessions")
    await db.delete(entry)


async def import_timetable_entries(
    db: AsyncSession,
    teacher_id: str,
    filename: str,
    content: bytes,
) -> dict:
    teacher = await get_teacher(db, teacher_id)
    rows = _read_timetable_rows(filename, content)
    created = 0
    skipped = 0

    for row in rows:
        try:
            data = TeacherTimetableCreate(
                class_id=row["class_id"],
                section_id=row["section_id"],
                subject_id=row["subject_id"],
                academic_year_id=row["academic_year_id"],
                day_of_week=row["day_of_week"],
                start_time=_parse_time(row["start_time"]),
                end_time=_parse_time(row["end_time"]),
                room_no=row.get("room_no") or None,
                version_no=int(row.get("version_no") or 1),
                is_active=str(row.get("is_active", "true")).lower() in ("true", "1", "yes"),
            )
            await create_timetable_entry(db, str(teacher.id), data)
            created += 1
        except Exception:
            skipped += 1

    return {"created": created, "skipped": skipped, "total": len(rows)}


async def remove_class(db: AsyncSession, teacher_id: str, class_id: str) -> None:
    teacher = await get_teacher(db, teacher_id)
    teacher_class = (
        await db.execute(
            select(TeacherClass).where(
                TeacherClass.teacher_id == teacher.id,
                TeacherClass.class_id == class_id,
            )
        )
    ).scalar_one_or_none()
    if not teacher_class:
        raise NotFoundError("Teacher class link not found")

    timetable_exists = (
        await db.execute(
            select(TeacherTimetable.id).where(
                TeacherTimetable.teacher_id == teacher.id,
                TeacherTimetable.class_id == class_id,
            )
        )
    ).first()
    if timetable_exists:
        raise BusinessRuleError("Remove timetable entries for this class before unlinking it")

    await db.delete(teacher_class)


async def _user_has_teacher_role(db: AsyncSession, user_id: str) -> bool:
    row = (
        await db.execute(
            select(Role.id)
            .join(UserRole, UserRole.role_id == Role.id)
            .where(UserRole.user_id == user_id, _teacher_role_filter())
            .limit(1)
        )
    ).first()
    return row is not None


async def _get_teacher_role(db: AsyncSession, institution_id: str) -> Role | None:
    return (
        await db.execute(
            select(Role).where(
                Role.institution_id == institution_id,
                _teacher_role_filter(),
            )
        )
    ).scalar_one_or_none()


def _teacher_role_filter():
    return or_(
        func.lower(Role.slug) == "teacher",
        func.lower(Role.name) == "teacher",
        func.lower(Role.name).like("%teacher%"),
    )


def _read_timetable_rows(filename: str, content: bytes) -> list[dict]:
    lower = filename.lower()
    if lower.endswith(".csv"):
        text = content.decode("utf-8-sig")
        reader = csv.DictReader(StringIO(text))
        return [dict(r) for r in reader]
    if lower.endswith(".xlsx"):
        try:
            from openpyxl import load_workbook
        except Exception as exc:
            raise ValidationError("XLSX support requires openpyxl. Install it in backend environment.") from exc
        wb = load_workbook(filename=BytesIO(content), data_only=True)
        ws = wb.active
        headers = [str(c.value).strip() if c.value is not None else "" for c in ws[1]]
        items: list[dict] = []
        for row in ws.iter_rows(min_row=2, values_only=True):
            if not any(v is not None and str(v).strip() for v in row):
                continue
            items.append({headers[i]: row[i] for i in range(min(len(headers), len(row)))})
        return items
    raise ValidationError("Only .csv or .xlsx files are supported")


def _parse_time(value) -> time:
    if isinstance(value, time):
        return value
    value = str(value or "").strip()
    if not value:
        raise ValidationError("Time value is required")
    hh, mm = value.split(":")[:2]
    return time(int(hh), int(mm))


async def _get_timetable_entry(db: AsyncSession, entry_id: str) -> TeacherTimetable:
    entry = (
        await db.execute(select(TeacherTimetable).where(TeacherTimetable.id == entry_id))
    ).scalar_one_or_none()
    if not entry:
        raise NotFoundError("Timetable entry not found")
    return entry


async def _validate_timetable_refs(
    db: AsyncSession,
    teacher: Teacher,
    class_id,
    section_id,
    subject_id,
    academic_year_id,
):
    class_obj = (
        await db.execute(select(Class).where(Class.id == class_id))
    ).scalar_one_or_none()
    if not class_obj:
        raise NotFoundError("Class not found")

    section_obj = (
        await db.execute(select(Section).where(Section.id == section_id))
    ).scalar_one_or_none()
    if not section_obj:
        raise NotFoundError("Section not found")
    if section_obj.class_id != class_obj.id:
        raise ValidationError("Section does not belong to the selected class")

    subject_obj = (
        await db.execute(select(Subject).where(Subject.id == subject_id))
    ).scalar_one_or_none()
    if not subject_obj:
        raise NotFoundError("Subject not found")
    if getattr(subject_obj, "class_id", None):
        if subject_obj.class_id != class_obj.id:
            raise ValidationError("Subject does not belong to the selected class")
    elif subject_obj.branch_id and class_obj.branch_id and subject_obj.branch_id != class_obj.branch_id:
        raise ValidationError("Subject does not belong to the class branch")
    if getattr(subject_obj, "course_id", None) and getattr(class_obj, "course_id", None):
        if subject_obj.course_id != class_obj.course_id:
            raise ValidationError("Subject course does not match selected class course")
    if subject_obj.academic_year_id and subject_obj.academic_year_id != academic_year_id:
        raise ValidationError("Subject does not belong to the selected academic year")
    if class_obj.academic_year_id and class_obj.academic_year_id != academic_year_id:
        raise ValidationError("Class does not belong to the selected academic year")

    class_link = (
        await db.execute(
            select(TeacherClass.id).where(
                TeacherClass.teacher_id == teacher.id,
                TeacherClass.class_id == class_obj.id,
            )
        )
    ).first()
    if not class_link:
        raise ValidationError("Teacher is not linked to the selected class")

    return class_obj, section_obj, subject_obj


async def _ensure_timetable_slot_available(
    db: AsyncSession,
    teacher_id,
    section_id,
    day_of_week: TimetableDay,
    start_time,
    end_time=None,
    exclude_id=None,
):
    teacher_filters = [
        TeacherTimetable.teacher_id == teacher_id,
        TeacherTimetable.day_of_week == day_of_week,
    ]
    section_filters = [
        TeacherTimetable.section_id == section_id,
        TeacherTimetable.day_of_week == day_of_week,
    ]
    if exclude_id:
        teacher_filters.append(TeacherTimetable.id != exclude_id)
        section_filters.append(TeacherTimetable.id != exclude_id)
    if end_time:
        teacher_filters.extend(
            [TeacherTimetable.start_time < end_time, TeacherTimetable.end_time > start_time]
        )
        section_filters.extend(
            [TeacherTimetable.start_time < end_time, TeacherTimetable.end_time > start_time]
        )
    else:
        teacher_filters.append(TeacherTimetable.start_time == start_time)
        section_filters.append(TeacherTimetable.start_time == start_time)

    teacher_conflict = (
        await db.execute(select(TeacherTimetable.id).where(*teacher_filters))
    ).first()
    if teacher_conflict:
        raise ConflictError("Teacher already has another timetable entry in this time slot")

    section_conflict = (
        await db.execute(select(TeacherTimetable.id).where(*section_filters))
    ).first()
    if section_conflict:
        raise ConflictError("Section already has another timetable entry in this time slot")


async def _ensure_teacher_subject_link(
    db: AsyncSession,
    teacher_id,
    subject_id,
    section_id,
    academic_year_id,
) -> TeacherSubject:
    link = (
        await db.execute(
            select(TeacherSubject).where(
                TeacherSubject.teacher_id == teacher_id,
                TeacherSubject.subject_id == subject_id,
                TeacherSubject.section_id == section_id,
                TeacherSubject.academic_year_id == academic_year_id,
            )
        )
    ).scalar_one_or_none()
    if link:
        return link

    link = TeacherSubject(
        teacher_id=teacher_id,
        subject_id=subject_id,
        section_id=section_id,
        academic_year_id=academic_year_id,
    )
    db.add(link)
    await db.flush()
    return link


def _validate_time_range(start_time, end_time):
    if end_time <= start_time:
        raise ValidationError("End time must be after start time")


def _date_to_day(value: date | None) -> TimetableDay | None:
    if not value:
        return None
    return TimetableDay(value.strftime("%A").lower())
