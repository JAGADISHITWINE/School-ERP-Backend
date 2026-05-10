from typing import Annotated
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.modules.exams import service
from app.modules.exams.schema import ExamCreate, ExamUpdate, ExamSubjectCreate, MarksUploadRequest, ExamOut, ExamSubjectOut, MarkOut
from app.core.dependencies import CurrentUser, require_permission
from app.constants.permissions import EXAM_CREATE, EXAM_MANAGE, MARKS_UPLOAD, MARKS_LOCK
from app.utils.response import ok, paginated
from app.utils.pagination import PaginationParams

router = APIRouter(prefix="/exams", tags=["Exams & Marks"])
DB = Annotated[AsyncSession, Depends(get_db)]


@router.post("", response_model=dict, dependencies=[Depends(require_permission(EXAM_CREATE))])
async def create_exam(payload: ExamCreate, db: DB):
    exam = await service.create_exam(db, payload)
    return ok(data=ExamOut.model_validate(exam).model_dump(), message="Exam created")


@router.get("", response_model=dict, dependencies=[Depends(require_permission(EXAM_MANAGE))])
async def list_exams(
    current_user: CurrentUser,
    db: DB,
    pagination: Annotated[PaginationParams, Depends()],
):
    exams, total = await service.list_exams(
        db, current_user["institution_id"], pagination.offset, pagination.page_size
    )
    return paginated(
        [ExamOut.model_validate(e).model_dump() for e in exams],
        total, pagination.page, pagination.page_size,
    )


@router.post("/marks", response_model=dict, dependencies=[Depends(require_permission(MARKS_UPLOAD))])
async def upload_marks(payload: MarksUploadRequest, current_user: CurrentUser, db: DB):
    count = await service.upload_marks(
        db,
        payload,
        actor_user_id=current_user["id"],
        institution_id=current_user["institution_id"],
    )
    return ok(data={"records_saved": count}, message="Marks uploaded")


@router.get("/marks/{exam_subject_id}", response_model=dict, dependencies=[Depends(require_permission(MARKS_UPLOAD))])
async def get_marks(exam_subject_id: str, db: DB):
    marks = await service.get_marks(db, exam_subject_id)
    return ok(data=[MarkOut.model_validate(m).model_dump() for m in marks])


@router.post("/{exam_id}/subjects", response_model=dict, dependencies=[Depends(require_permission(EXAM_MANAGE))])
async def add_exam_subject(exam_id: str, payload: ExamSubjectCreate, db: DB):
    es = await service.add_exam_subject(db, exam_id, payload)
    return ok(data={"id": str(es.id)}, message="Subject added to exam")


@router.get("/{exam_id}/subjects", response_model=dict, dependencies=[Depends(require_permission(EXAM_MANAGE))])
async def list_exam_subjects(exam_id: str, db: DB):
    items = await service.list_exam_subjects(db, exam_id)
    return ok(data=[ExamSubjectOut.model_validate(i).model_dump() for i in items])


@router.get("/{exam_id}", response_model=dict, dependencies=[Depends(require_permission(EXAM_MANAGE))])
async def get_exam(exam_id: str, db: DB):
    exam = await service.get_exam(db, exam_id)
    return ok(data=ExamOut.model_validate(exam).model_dump())


@router.patch("/{exam_id}/workflow/{action}", response_model=dict, dependencies=[Depends(require_permission(MARKS_LOCK))])
async def advance_workflow(exam_id: str, action: str, current_user: CurrentUser, db: DB):
    """action = 'submit' or 'lock'"""
    exam = await service.advance_workflow(
        db,
        exam_id,
        action,
        actor_user_id=current_user["id"],
        institution_id=current_user["institution_id"],
    )
    return ok(data=ExamOut.model_validate(exam).model_dump(), message=f"Exam {action}ted")
