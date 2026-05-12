from typing import Annotated
from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.session import get_db
from app.modules.students import service
from app.modules.students.schema import (
    StudentCreate,
    StudentUpdate,
    StudentStatusUpdate,
    StudentDocumentCreate,
    StudentDocumentUpdate,
    StudentDocumentOut,
    AcademicRecordCreate,
    StudentOut,
    AcademicRecordOut,
    AcademicRecordListItem,
    PromotionExecuteRequest,
    PromotionPreviewRequest,
)
from app.modules.users.model import User
from app.modules.students.model import StudentAcademicRecord
from app.modules.academic.model import Branch, Class, Section, AcademicYear
from app.modules.roles.model import Role, UserRole
from app.core.dependencies import CurrentUser, require_permission
from app.core.role_context import has_any_role
from app.constants.permissions import STUDENT_CREATE, STUDENT_READ, STUDENT_UPDATE
from app.modules.logs.service import log_activity
from app.utils.response import ok, paginated
from app.utils.pagination import PaginationParams

router = APIRouter(prefix="/students", tags=["Students"])

DB = Annotated[AsyncSession, Depends(get_db)]
Pagination = Annotated[PaginationParams, Depends()]


async def _current_academic_snapshot(db: AsyncSession, student_id):
    row = (
        await db.execute(
            select(
                StudentAcademicRecord.branch_id,
                Branch.name,
                StudentAcademicRecord.section_id,
                Section.name,
                Class.id,
                Class.name,
                Class.course_id,
                StudentAcademicRecord.academic_year_id,
                AcademicYear.label,
                StudentAcademicRecord.status,
            )
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
        "current_branch_id": str(row[0]) if row[0] else None,
        "current_branch_name": row[1],
        "current_section_id": str(row[2]) if row[2] else None,
        "current_section_name": row[3],
        "current_class_id": str(row[4]) if row[4] else None,
        "current_class_name": row[5],
        "current_course_id": str(row[6]) if row[6] else None,
        "current_academic_year_id": str(row[7]) if row[7] else None,
        "current_academic_year_label": row[8],
        "current_status": row[9],
    }


async def _user_role_slug(db: AsyncSession, user_id):
    row = (
        await db.execute(
            select(Role.slug)
            .join(UserRole, UserRole.role_id == Role.id)
            .where(UserRole.user_id == user_id)
            .limit(1)
        )
    ).first()
    return row[0] if row else None


@router.post("", response_model=dict, dependencies=[Depends(require_permission(STUDENT_CREATE))])
async def create_student(payload: StudentCreate, db: DB):
    student = await service.create_student(db, payload)
    return ok(data={"id": str(student.id)}, message="Student created")


@router.get("", response_model=dict, dependencies=[Depends(require_permission(STUDENT_READ))])
async def list_students(
    current_user: CurrentUser,
    db: DB,
    pagination: Pagination,
    search: str | None = Query(default=None),
):
    if not current_user["is_superuser"] and has_any_role(current_user, {"hod"}):
        students, total = await service.list_students_for_hod(
            db, current_user["institution_id"], current_user["id"], pagination.offset, pagination.page_size, search
        )
    elif not current_user["is_superuser"] and has_any_role(current_user, {"teacher"}):
        students, total = await service.list_students_for_teacher(
            db, current_user["institution_id"], current_user["id"], pagination.offset, pagination.page_size, search
        )
    else:
        students, total = await service.list_students(
            db, current_user["institution_id"], pagination.offset, pagination.page_size, search
        )
    out = []
    for s in students:
        user = (await db.execute(select(User).where(User.id == s.user_id))).scalar_one()
        current = await _current_academic_snapshot(db, s.id)
        role_slug = await _user_role_slug(db, s.user_id)
        d = {
            "id": str(s.id),
            "user_id": str(s.user_id),
            "institution_id": str(user.institution_id),
            "roll_number": s.roll_number,
            "date_of_birth": s.date_of_birth,
            "gender": s.gender,
            "guardian_name": s.guardian_name,
            "guardian_phone": s.guardian_phone,
            "guardian_email": s.guardian_email,
            "full_name": user.full_name,
            "email": user.email,
            "phone": user.phone,
            "role_slug": role_slug,
            "created_at": s.created_at,
            "updated_at": s.updated_at,
            **current,
        }
        out.append(d)
    return paginated(out, total, pagination.page, pagination.page_size)


@router.get("/documents/list", response_model=dict, dependencies=[Depends(require_permission(STUDENT_READ))])
async def list_student_documents(current_user: CurrentUser, db: DB, pagination: Pagination):
    rows, total = await service.list_documents(
        db, current_user["institution_id"], pagination.offset, pagination.page_size
    )
    out = []
    for document, student_name, roll_number in rows:
        data = StudentDocumentOut.model_validate(document).model_dump()
        data["student_name"] = student_name
        data["roll_number"] = roll_number
        out.append(data)
    return paginated(out, total, pagination.page, pagination.page_size)


@router.get("/self/portal", response_model=dict)
async def get_my_student_portal(current_user: CurrentUser, db: DB):
    data = await service.get_student_portal(db, current_user)
    return ok(data=data)


@router.post("/promotions/preview", response_model=dict, dependencies=[Depends(require_permission(STUDENT_READ))])
async def preview_student_promotion(payload: PromotionPreviewRequest, current_user: CurrentUser, db: DB):
    data = await service.preview_promotion(db, current_user["institution_id"], payload)
    return ok(data=data)


@router.post("/promotions/execute", response_model=dict, dependencies=[Depends(require_permission(STUDENT_UPDATE))])
async def execute_student_promotion(payload: PromotionExecuteRequest, current_user: CurrentUser, db: DB):
    data = await service.execute_promotion(db, current_user["institution_id"], payload, actor_user_id=current_user["id"])
    return ok(data=data, message="Student promotion completed")


@router.get("/{student_id}/full-profile", response_model=dict, dependencies=[Depends(require_permission(STUDENT_READ))])
async def get_student_full_profile(student_id: str, current_user: CurrentUser, db: DB):
    await service.assert_can_view_student(db, current_user, student_id)
    data = await service.get_student_full_profile(db, student_id)
    return ok(data=data)


@router.post("/documents", response_model=dict, dependencies=[Depends(require_permission(STUDENT_UPDATE))])
async def create_student_document(payload: StudentDocumentCreate, current_user: CurrentUser, db: DB):
    document = await service.create_document(db, payload)
    await log_activity(
        db,
        module="students",
        action="document_create",
        actor_user_id=current_user["id"],
        institution_id=current_user["institution_id"],
        entity_type="student_document",
        entity_id=str(document.id),
        message="Student document metadata added",
        meta={"student_id": str(payload.student_id), "document_type": payload.document_type},
    )
    return ok(data={"id": str(document.id)}, message="Student document added")


@router.post("/documents/upload", response_model=dict, dependencies=[Depends(require_permission(STUDENT_UPDATE))])
async def upload_student_document(
    current_user: CurrentUser,
    db: DB,
    student_id: Annotated[str, Form()],
    document_type: Annotated[str, Form()],
    title: Annotated[str, Form()],
    status: Annotated[str, Form()] = "pending",
    remarks: Annotated[str | None, Form()] = None,
    file: UploadFile = File(...),
):
    content = await file.read()
    document = await service.store_document_file(
        db,
        student_id=student_id,
        document_type=document_type,
        title=title,
        status=status,
        remarks=remarks,
        original_name=file.filename or "document",
        content_type=file.content_type,
        content=content,
        actor_user_id=current_user["id"],
        institution_id=current_user["institution_id"],
    )
    return ok(data=StudentDocumentOut.model_validate(document).model_dump(), message="Student document uploaded")


@router.get("/documents/{document_id}/download", dependencies=[Depends(require_permission(STUDENT_READ))])
async def download_student_document(document_id: str, current_user: CurrentUser, db: DB):
    document, file_path = await service.get_document_file(db, document_id, current_user["institution_id"])
    await log_activity(
        db,
        module="students",
        action="document_download",
        actor_user_id=current_user["id"],
        institution_id=current_user["institution_id"],
        entity_type="student_document",
        entity_id=str(document.id),
        message="Student document downloaded",
        meta={"student_id": str(document.student_id), "file_name": document.file_name},
    )
    return FileResponse(path=file_path, filename=document.file_name or file_path.name)


@router.patch("/documents/{document_id}", response_model=dict, dependencies=[Depends(require_permission(STUDENT_UPDATE))])
async def update_student_document(document_id: str, payload: StudentDocumentUpdate, current_user: CurrentUser, db: DB):
    document = await service.update_document(db, document_id, payload)
    await log_activity(
        db,
        module="students",
        action="document_update",
        actor_user_id=current_user["id"],
        institution_id=current_user["institution_id"],
        entity_type="student_document",
        entity_id=str(document.id),
        message="Student document updated",
        meta=payload.model_dump(exclude_none=True),
    )
    return ok(data={"id": str(document.id)}, message="Student document updated")


@router.delete("/documents/{document_id}", response_model=dict, dependencies=[Depends(require_permission(STUDENT_UPDATE))])
async def delete_student_document(document_id: str, current_user: CurrentUser, db: DB):
    await service.delete_document(db, document_id)
    await log_activity(
        db,
        module="students",
        action="document_delete",
        actor_user_id=current_user["id"],
        institution_id=current_user["institution_id"],
        entity_type="student_document",
        entity_id=document_id,
        message="Student document deleted",
    )
    return ok(message="Student document deleted")


@router.get("/{student_id}", response_model=dict, dependencies=[Depends(require_permission(STUDENT_READ))])
async def get_student(student_id: str, current_user: CurrentUser, db: DB):
    await service.assert_can_view_student(db, current_user, student_id)
    student = await service.get_student(db, student_id)
    user = (await db.execute(select(User).where(User.id == student.user_id))).scalar_one()
    current = await _current_academic_snapshot(db, student.id)
    role_slug = await _user_role_slug(db, student.user_id)
    d = {
        "id": str(student.id),
        "user_id": str(student.user_id),
        "institution_id": str(user.institution_id),
        "roll_number": student.roll_number,
        "date_of_birth": student.date_of_birth,
        "gender": student.gender,
        "guardian_name": student.guardian_name,
        "guardian_phone": student.guardian_phone,
        "guardian_email": student.guardian_email,
        "full_name": user.full_name,
        "email": user.email,
        "phone": user.phone,
        "role_slug": role_slug,
        "created_at": student.created_at,
        "updated_at": student.updated_at,
        **current,
    }
    return ok(data=d)


@router.patch("/{student_id}", response_model=dict, dependencies=[Depends(require_permission(STUDENT_UPDATE))])
async def update_student(student_id: str, payload: StudentUpdate, current_user: CurrentUser, db: DB):
    student = await service.update_student(db, student_id, payload)
    await log_activity(
        db,
        module="students",
        action="student_update",
        actor_user_id=current_user["id"],
        institution_id=current_user["institution_id"],
        entity_type="student",
        entity_id=str(student.id),
        message="Student profile updated",
        meta=payload.model_dump(exclude_none=True),
    )
    return ok(data={"id": str(student.id)}, message="Student updated")


@router.delete("/{student_id}", response_model=dict, dependencies=[Depends(require_permission(STUDENT_UPDATE))])
async def delete_student(student_id: str, current_user: CurrentUser, db: DB):
    await service.delete_student(db, student_id)
    await log_activity(
        db,
        module="students",
        action="student_deactivate",
        actor_user_id=current_user["id"],
        institution_id=current_user["institution_id"],
        entity_type="student",
        entity_id=student_id,
        message="Student deactivated",
    )
    return ok(message="Student deactivated")


@router.patch("/{student_id}/status", response_model=dict, dependencies=[Depends(require_permission(STUDENT_UPDATE))])
async def update_student_status(student_id: str, payload: StudentStatusUpdate, current_user: CurrentUser, db: DB):
    record = await service.update_student_status(db, student_id, payload.status)
    await log_activity(
        db,
        module="students",
        action="student_status_update",
        actor_user_id=current_user["id"],
        institution_id=current_user["institution_id"],
        entity_type="student",
        entity_id=student_id,
        message="Student status updated",
        meta={"status": payload.status},
    )
    return ok(
        data={
            "student_id": str(record.student_id),
            "academic_record_id": str(record.id),
            "status": record.status,
            "exited_at": record.exited_at,
        },
        message="Student status updated",
    )


@router.post("/{student_id}/academic-record", response_model=dict, dependencies=[Depends(require_permission(STUDENT_UPDATE))])
async def add_academic_record(student_id: str, payload: AcademicRecordCreate, current_user: CurrentUser, db: DB):
    record = await service.create_academic_record(db, student_id, payload)
    await log_activity(
        db,
        module="students",
        action="academic_record_create",
        actor_user_id=current_user["id"],
        institution_id=current_user["institution_id"],
        entity_type="student_academic_record",
        entity_id=str(record.id),
        message="Student academic record created",
        meta=payload.model_dump(),
    )
    return ok(data=AcademicRecordOut.model_validate(record).model_dump(), message="Academic record added")


@router.get("/{student_id}/academic-records", response_model=dict, dependencies=[Depends(require_permission(STUDENT_READ))])
async def list_student_academic_records(student_id: str, db: DB):
    records = await service.list_academic_records(db, student_id)
    out = []
    for record in records:
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
        out.append({
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
            "status": record.status,
            "enrolled_at": record.enrolled_at,
            "exited_at": record.exited_at,
        })
    return ok(data=out)
