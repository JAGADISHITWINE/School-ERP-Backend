from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import CurrentUser
from app.core.exceptions import ForbiddenError
from app.db.session import get_db
from app.modules.teacher_content import service
from app.modules.teacher_content.model import AssessmentType, MaterialType
from app.modules.teacher_content.schema import AssessmentCreate, AssignmentCreate, MaterialCreate
from app.utils.pagination import PaginationParams
from app.utils.response import ok, paginated

router = APIRouter(prefix="/teacher-content", tags=["Teacher Academic Content"])
DB = Annotated[AsyncSession, Depends(get_db)]
Pagination = Annotated[PaginationParams, Depends()]


async def _require_role(db: AsyncSession, current_user: dict, *roles: str):
    if current_user["is_superuser"]:
        return
    if not await service.user_has_role(db, current_user["id"], *roles):
        raise ForbiddenError("Role not allowed for this action")


def _filters(
    academic_year_id: str | None = None,
    class_id: str | None = None,
    section_id: str | None = None,
    subject_id: str | None = None,
    from_date: date | None = None,
    to_date: date | None = None,
) -> dict:
    return {
        "academic_year_id": academic_year_id,
        "class_id": class_id,
        "section_id": section_id,
        "subject_id": subject_id,
        "from_date": from_date,
        "to_date": to_date,
    }


def _item(row):
    mapping = row._mapping
    data = row[0].__dict__.copy()
    data.pop("_sa_instance_state", None)
    data.update(
        {
            "academic_year_label": mapping.get("academic_year_label"),
            "branch_name": mapping.get("branch_name"),
            "class_name": mapping.get("class_name"),
            "section_name": mapping.get("section_name"),
            "subject_name": mapping.get("subject_name"),
        }
    )
    if "submission_count" in mapping:
        data["submission_count"] = int(mapping.get("submission_count") or 0)
    if "submitted" in mapping:
        data["submitted"] = bool(mapping.get("submitted"))
    return data


@router.get("/teacher/dropdowns", response_model=dict)
async def teacher_dropdowns(current_user: CurrentUser, db: DB):
    await _require_role(db, current_user, "teacher")
    return ok(data=await service.assigned_dropdowns(db, current_user["id"]))


@router.post("/teacher/materials", response_model=dict)
async def create_material(
    current_user: CurrentUser,
    db: DB,
    title: Annotated[str, Form()],
    academic_year_id: Annotated[str, Form()],
    branch_id: Annotated[str, Form()],
    class_id: Annotated[str, Form()],
    section_id: Annotated[str, Form()],
    subject_id: Annotated[str, Form()],
    material_type: Annotated[MaterialType, Form()],
    description: Annotated[str | None, Form()] = None,
    external_url: Annotated[str | None, Form()] = None,
    file: UploadFile | None = File(default=None),
):
    await _require_role(db, current_user, "teacher")
    content = await file.read() if file else None
    payload = MaterialCreate(
        title=title,
        description=description,
        academic_year_id=academic_year_id,
        branch_id=branch_id,
        class_id=class_id,
        section_id=section_id,
        subject_id=subject_id,
        material_type=material_type,
        external_url=external_url,
    )
    item = await service.create_material(
        db,
        current_user["id"],
        payload,
        original_name=file.filename if file else None,
        content_type=file.content_type if file else None,
        content=content,
    )
    return ok(data={"id": str(item.id)}, message="Material uploaded")


@router.get("/teacher/materials", response_model=dict)
async def list_teacher_materials(
    current_user: CurrentUser,
    db: DB,
    pagination: Pagination,
    academic_year_id: str | None = None,
    class_id: str | None = None,
    section_id: str | None = None,
    subject_id: str | None = None,
):
    await _require_role(db, current_user, "teacher")
    rows, total = await service.list_teacher_materials(
        db, current_user["id"], _filters(academic_year_id, class_id, section_id, subject_id), pagination.offset, pagination.page_size
    )
    return paginated([_item(row) for row in rows], total, pagination.page, pagination.page_size)


@router.post("/teacher/assessments", response_model=dict)
async def create_assessment(
    current_user: CurrentUser,
    db: DB,
    title: Annotated[str, Form()],
    academic_year_id: Annotated[str, Form()],
    branch_id: Annotated[str, Form()],
    class_id: Annotated[str, Form()],
    section_id: Annotated[str, Form()],
    subject_id: Annotated[str, Form()],
    assessment_type: Annotated[AssessmentType, Form()],
    total_marks: Annotated[int, Form()],
    due_date: Annotated[date, Form()],
    description: Annotated[str | None, Form()] = None,
    instructions: Annotated[str | None, Form()] = None,
    file: UploadFile | None = File(default=None),
):
    await _require_role(db, current_user, "teacher")
    content = await file.read() if file else None
    payload = AssessmentCreate(
        title=title,
        description=description,
        academic_year_id=academic_year_id,
        branch_id=branch_id,
        class_id=class_id,
        section_id=section_id,
        subject_id=subject_id,
        assessment_type=assessment_type,
        total_marks=total_marks,
        due_date=due_date,
        instructions=instructions,
    )
    item = await service.create_assessment(
        db,
        current_user["id"],
        payload,
        original_name=file.filename if file else None,
        content_type=file.content_type if file else None,
        content=content,
    )
    return ok(data={"id": str(item.id)}, message="Assessment created")


@router.get("/teacher/assessments", response_model=dict)
async def list_teacher_assessments(
    current_user: CurrentUser,
    db: DB,
    pagination: Pagination,
    academic_year_id: str | None = None,
    class_id: str | None = None,
    section_id: str | None = None,
    subject_id: str | None = None,
    from_date: date | None = None,
    to_date: date | None = None,
):
    await _require_role(db, current_user, "teacher")
    rows, total = await service.list_teacher_assessments(
        db, current_user["id"], _filters(academic_year_id, class_id, section_id, subject_id, from_date, to_date), pagination.offset, pagination.page_size
    )
    return paginated([_item(row) for row in rows], total, pagination.page, pagination.page_size)


@router.post("/teacher/assignments", response_model=dict)
async def create_assignment(
    current_user: CurrentUser,
    db: DB,
    title: Annotated[str, Form()],
    academic_year_id: Annotated[str, Form()],
    branch_id: Annotated[str, Form()],
    class_id: Annotated[str, Form()],
    section_id: Annotated[str, Form()],
    subject_id: Annotated[str, Form()],
    total_marks: Annotated[int, Form()],
    due_date: Annotated[date, Form()],
    description: Annotated[str | None, Form()] = None,
    instructions: Annotated[str | None, Form()] = None,
    file: UploadFile | None = File(default=None),
):
    await _require_role(db, current_user, "teacher")
    content = await file.read() if file else None
    payload = AssignmentCreate(
        title=title,
        description=description,
        academic_year_id=academic_year_id,
        branch_id=branch_id,
        class_id=class_id,
        section_id=section_id,
        subject_id=subject_id,
        total_marks=total_marks,
        due_date=due_date,
        instructions=instructions,
    )
    item = await service.create_assignment(
        db,
        current_user["id"],
        payload,
        original_name=file.filename if file else None,
        content_type=file.content_type if file else None,
        content=content,
    )
    return ok(data={"id": str(item.id)}, message="Assignment created")


@router.get("/teacher/assignments", response_model=dict)
async def list_teacher_assignments(
    current_user: CurrentUser,
    db: DB,
    pagination: Pagination,
    academic_year_id: str | None = None,
    class_id: str | None = None,
    section_id: str | None = None,
    subject_id: str | None = None,
    from_date: date | None = None,
    to_date: date | None = None,
):
    await _require_role(db, current_user, "teacher")
    rows, total = await service.list_teacher_assignments(
        db, current_user["id"], _filters(academic_year_id, class_id, section_id, subject_id, from_date, to_date), pagination.offset, pagination.page_size
    )
    return paginated([_item(row) for row in rows], total, pagination.page, pagination.page_size)


@router.get("/teacher/assignments/{assignment_id}/submissions", response_model=dict)
async def list_submissions(assignment_id: str, current_user: CurrentUser, db: DB):
    await _require_role(db, current_user, "teacher")
    rows = await service.list_assignment_submissions(db, current_user["id"], assignment_id)
    data = []
    for submission, student_name, roll_number in rows:
        item = submission.__dict__.copy()
        item.pop("_sa_instance_state", None)
        item["student_name"] = student_name
        item["roll_number"] = roll_number
        data.append(item)
    return ok(data=data)


@router.get("/student/materials", response_model=dict)
async def list_student_materials(
    current_user: CurrentUser,
    db: DB,
    pagination: Pagination,
    academic_year_id: str | None = None,
    class_id: str | None = None,
    section_id: str | None = None,
    subject_id: str | None = None,
):
    await _require_role(db, current_user, "student")
    rows, total = await service.list_student_materials(
        db, current_user["id"], _filters(academic_year_id, class_id, section_id, subject_id), pagination.offset, pagination.page_size
    )
    return paginated([_item(row) for row in rows], total, pagination.page, pagination.page_size)


@router.get("/student/assessments", response_model=dict)
async def list_student_assessments(
    current_user: CurrentUser,
    db: DB,
    pagination: Pagination,
    academic_year_id: str | None = None,
    class_id: str | None = None,
    section_id: str | None = None,
    subject_id: str | None = None,
    from_date: date | None = None,
    to_date: date | None = None,
):
    await _require_role(db, current_user, "student")
    rows, total = await service.list_student_assessments(
        db, current_user["id"], _filters(academic_year_id, class_id, section_id, subject_id, from_date, to_date), pagination.offset, pagination.page_size
    )
    return paginated([_item(row) for row in rows], total, pagination.page, pagination.page_size)


@router.get("/student/assignments", response_model=dict)
async def list_student_assignments(
    current_user: CurrentUser,
    db: DB,
    pagination: Pagination,
    academic_year_id: str | None = None,
    class_id: str | None = None,
    section_id: str | None = None,
    subject_id: str | None = None,
    from_date: date | None = None,
    to_date: date | None = None,
):
    await _require_role(db, current_user, "student")
    rows, total = await service.list_student_assignments(
        db, current_user["id"], _filters(academic_year_id, class_id, section_id, subject_id, from_date, to_date), pagination.offset, pagination.page_size
    )
    return paginated([_item(row) for row in rows], total, pagination.page, pagination.page_size)


@router.post("/student/assignments/{assignment_id}/submit", response_model=dict)
async def submit_assignment(
    assignment_id: str,
    current_user: CurrentUser,
    db: DB,
    remarks: Annotated[str | None, Form()] = None,
    file: UploadFile | None = File(default=None),
):
    await _require_role(db, current_user, "student")
    content = await file.read() if file else None
    item = await service.submit_assignment(
        db,
        current_user["id"],
        assignment_id,
        remarks,
        original_name=file.filename if file else None,
        content_type=file.content_type if file else None,
        content=content,
    )
    return ok(data={"id": str(item.id)}, message="Assignment submitted")


@router.get("/files/{table}/{item_id}/download")
async def download_file(table: str, item_id: str, current_user: CurrentUser, db: DB):
    if table not in {"materials", "assessments", "assignments", "submissions"}:
        raise ForbiddenError("Invalid file type")
    filename, path = await service.get_content_file(db, table, item_id, current_user["id"], current_user["institution_id"])
    return FileResponse(path=path, filename=filename)
