from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, update, or_
from app.modules.exams.model import Exam, ExamSubject, Mark, ExamWorkflow
from app.modules.exams.schema import ExamCreate, ExamUpdate, ExamSubjectCreate, MarksUploadRequest
from app.core.exceptions import NotFoundError, BusinessRuleError
from app.modules.logs.service import log_activity
from app.modules.students.model import Student, StudentAcademicRecord, StudentStatus
from app.modules.users.model import User
from app.modules.roles.model import Role, UserRole
from app.modules.academic.model import Section, Subject
from app.modules.teachers.model import Teacher, TeacherClass, TeacherSubject, TeacherTimetable


async def create_exam(db: AsyncSession, data: ExamCreate) -> Exam:
    exam = Exam(**data.model_dump())
    db.add(exam)
    await db.flush()
    await db.refresh(exam)
    return exam


async def list_exams(db: AsyncSession, institution_id: str, offset: int, limit: int):
    q = select(Exam).where(Exam.institution_id == institution_id)
    total = (await db.execute(select(func.count()).select_from(q.subquery()))).scalar()
    result = await db.execute(q.order_by(Exam.created_at.desc()).offset(offset).limit(limit))
    return result.scalars().all(), total


async def get_exam(db: AsyncSession, exam_id: str) -> Exam:
    exam = (await db.execute(select(Exam).where(Exam.id == exam_id))).scalar_one_or_none()
    if not exam:
        raise NotFoundError("Exam not found")
    return exam


async def add_exam_subject(db: AsyncSession, exam_id: str, data: ExamSubjectCreate) -> ExamSubject:
    exam = await get_exam(db, exam_id)
    if exam.workflow_status == ExamWorkflow.LOCKED:
        raise BusinessRuleError("Cannot modify a locked exam")
    es = ExamSubject(exam_id=exam_id, **data.model_dump())
    db.add(es)
    await db.flush()
    await db.refresh(es)
    return es


async def list_exam_subjects(db: AsyncSession, exam_id: str) -> list[ExamSubject]:
    await get_exam(db, exam_id)
    result = await db.execute(
        select(ExamSubject).where(ExamSubject.exam_id == exam_id)
    )
    return result.scalars().all()


async def advance_workflow(
    db: AsyncSession,
    exam_id: str,
    action: str,
    actor_user_id: str | None = None,
    institution_id: str | None = None,
) -> Exam:
    exam = await get_exam(db, exam_id)
    transitions = {
        "submit": (ExamWorkflow.DRAFT, ExamWorkflow.SUBMITTED),
        "lock":   (ExamWorkflow.SUBMITTED, ExamWorkflow.LOCKED),
    }
    if action not in transitions:
        raise BusinessRuleError(f"Unknown action: {action}")
    expected, next_status = transitions[action]
    if exam.workflow_status != expected:
        raise BusinessRuleError(
            f"Cannot {action} from status '{exam.workflow_status}'. Expected '{expected}'"
        )
    exam.workflow_status = next_status
    if next_status == ExamWorkflow.LOCKED:
        await db.execute(
            update(Mark)
            .where(Mark.exam_subject_id.in_(select(ExamSubject.id).where(ExamSubject.exam_id == exam.id)))
            .values(is_locked=True)
        )
    await db.flush()
    await log_activity(
        db,
        module="exams",
        action=f"exam_{action}",
        actor_user_id=actor_user_id,
        institution_id=institution_id,
        entity_type="exam",
        entity_id=str(exam.id),
        message=f"Exam {action} workflow action completed",
        meta={"next_status": next_status},
    )
    return exam


async def upload_marks(
    db: AsyncSession,
    data: MarksUploadRequest,
    actor_user_id: str | None = None,
    institution_id: str | None = None,
) -> int:
    # Validate exam subject exists and exam is not locked
    es = (
        await db.execute(select(ExamSubject).where(ExamSubject.id == data.exam_subject_id))
    ).scalar_one_or_none()
    if not es:
        raise NotFoundError("ExamSubject not found")

    exam = await get_exam(db, str(es.exam_id))
    if institution_id and str(exam.institution_id) != str(institution_id):
        raise BusinessRuleError("Exam does not belong to your institution")
    if exam.workflow_status != ExamWorkflow.DRAFT:
        raise BusinessRuleError("Marks can be uploaded only while exam is in draft status")
    teacher = await _teacher_for_user(db, actor_user_id)
    if teacher:
        allowed = await _teacher_can_upload_exam_subject(db, str(teacher.id), es)
        if not allowed:
            raise BusinessRuleError("Teacher is not assigned to this exam subject")

    # Upsert marks per student
    for entry in data.entries:
        existing = (
            await db.execute(
                select(Mark).where(
                    Mark.exam_subject_id == data.exam_subject_id,
                    Mark.student_id == entry.student_id,
                )
            )
        ).scalar_one_or_none()
        if existing and existing.is_locked:
            raise BusinessRuleError("Cannot modify a locked mark record")
        student = (
            await db.execute(
                select(Student)
                .join(User, User.id == Student.user_id)
                .where(Student.id == entry.student_id, User.institution_id == exam.institution_id)
            )
        ).scalar_one_or_none()
        if not student:
            raise BusinessRuleError("Student does not belong to this institution")
        if teacher:
            allowed_student = await _teacher_can_mark_student(db, str(teacher.id), es, str(entry.student_id))
            if not allowed_student:
                raise BusinessRuleError("One or more students are outside this teacher assignment")
        if not entry.is_absent:
            if entry.marks_obtained is None:
                raise BusinessRuleError("Marks are required when student is not absent")
            if entry.marks_obtained < 0 or entry.marks_obtained > es.max_marks:
                raise BusinessRuleError(f"Marks must be between 0 and {es.max_marks}")

        if existing:
            existing.marks_obtained = None if entry.is_absent else entry.marks_obtained
            existing.is_absent = entry.is_absent
        else:
            mark = Mark(
                exam_subject_id=str(data.exam_subject_id),
                student_id=str(entry.student_id),
                marks_obtained=None if entry.is_absent else entry.marks_obtained,
                is_absent=entry.is_absent,
            )
            db.add(mark)

    await db.flush()
    await log_activity(
        db,
        module="exams",
        action="marks_upload",
        actor_user_id=actor_user_id,
        institution_id=institution_id,
        entity_type="exam_subject",
        entity_id=str(data.exam_subject_id),
        message="Marks uploaded",
        meta={"records_saved": len(data.entries), "exam_id": str(es.exam_id)},
    )
    return len(data.entries)


async def get_marks(db: AsyncSession, exam_subject_id: str) -> list[Mark]:
    result = await db.execute(
        select(Mark).where(Mark.exam_subject_id == exam_subject_id)
    )
    return result.scalars().all()


async def _teacher_for_user(db: AsyncSession, user_id: str | None) -> Teacher | None:
    if not user_id:
        return None
    role_slug = (
        await db.execute(
            select(Role.slug)
            .join(UserRole, UserRole.role_id == Role.id)
            .where(UserRole.user_id == user_id)
            .limit(1)
        )
    ).scalar_one_or_none()
    if role_slug != "teacher":
        return None
    return (
        await db.execute(select(Teacher).where(Teacher.user_id == user_id))
    ).scalar_one_or_none()


async def _teacher_can_upload_exam_subject(db: AsyncSession, teacher_id: str, exam_subject: ExamSubject) -> bool:
    subject = (
        await db.execute(select(Subject).where(Subject.id == exam_subject.subject_id))
    ).scalar_one_or_none()
    if not subject:
        return False
    row = (
        await db.execute(
            select(TeacherSubject.id)
            .where(
                TeacherSubject.teacher_id == teacher_id,
                TeacherSubject.subject_id == exam_subject.subject_id,
            )
            .union(
                select(TeacherTimetable.id).where(
                    TeacherTimetable.teacher_id == teacher_id,
                    TeacherTimetable.subject_id == exam_subject.subject_id,
                    TeacherTimetable.is_active == True,
                )
            )
            .union(
                select(TeacherClass.id).where(
                    TeacherClass.teacher_id == teacher_id,
                    TeacherClass.class_id == subject.class_id,
                )
            )
            .limit(1)
        )
    ).first()
    return bool(row)


async def _teacher_can_mark_student(db: AsyncSession, teacher_id: str, exam_subject: ExamSubject, student_id: str) -> bool:
    subject = (
        await db.execute(select(Subject).where(Subject.id == exam_subject.subject_id))
    ).scalar_one_or_none()
    if not subject:
        return False
    row = (
        await db.execute(
            select(StudentAcademicRecord.id)
            .join(Section, Section.id == StudentAcademicRecord.section_id)
            .where(
                StudentAcademicRecord.student_id == student_id,
                StudentAcademicRecord.exited_at == None,
                StudentAcademicRecord.status == StudentStatus.ACTIVE,
                Section.class_id == subject.class_id,
                or_(
                    StudentAcademicRecord.section_id.in_(
                        select(TeacherSubject.section_id).where(
                            TeacherSubject.teacher_id == teacher_id,
                            TeacherSubject.subject_id == exam_subject.subject_id,
                        )
                    ),
                    StudentAcademicRecord.section_id.in_(
                        select(TeacherTimetable.section_id).where(
                            TeacherTimetable.teacher_id == teacher_id,
                            TeacherTimetable.subject_id == exam_subject.subject_id,
                            TeacherTimetable.is_active == True,
                        )
                    ),
                    Section.class_id.in_(
                        select(TeacherClass.class_id).where(TeacherClass.teacher_id == teacher_id)
                    ),
                ),
            )
            .limit(1)
        )
    ).first()
    return bool(row)
