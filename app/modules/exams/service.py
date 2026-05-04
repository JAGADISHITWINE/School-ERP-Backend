from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, insert
from app.modules.exams.model import Exam, ExamSubject, Mark, ExamWorkflow
from app.modules.exams.schema import ExamCreate, ExamUpdate, ExamSubjectCreate, MarksUploadRequest
from app.core.exceptions import NotFoundError, BusinessRuleError


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


async def advance_workflow(db: AsyncSession, exam_id: str, action: str) -> Exam:
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
    await db.flush()
    return exam


async def upload_marks(db: AsyncSession, data: MarksUploadRequest) -> int:
    # Validate exam subject exists and exam is not locked
    es = (
        await db.execute(select(ExamSubject).where(ExamSubject.id == data.exam_subject_id))
    ).scalar_one_or_none()
    if not es:
        raise NotFoundError("ExamSubject not found")

    exam = await get_exam(db, str(es.exam_id))
    if exam.workflow_status == ExamWorkflow.LOCKED:
        raise BusinessRuleError("Marks are locked for this exam")

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

        if existing:
            existing.marks_obtained = entry.marks_obtained
            existing.is_absent = entry.is_absent
        else:
            mark = Mark(
                exam_subject_id=str(data.exam_subject_id),
                student_id=str(entry.student_id),
                marks_obtained=entry.marks_obtained,
                is_absent=entry.is_absent,
            )
            db.add(mark)

    await db.flush()
    return len(data.entries)


async def get_marks(db: AsyncSession, exam_subject_id: str) -> list[Mark]:
    result = await db.execute(
        select(Mark).where(Mark.exam_subject_id == exam_subject_id)
    )
    return result.scalars().all()
