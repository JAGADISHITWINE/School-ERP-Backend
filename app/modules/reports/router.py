from typing import Annotated
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from io import StringIO
import csv
from app.db.session import get_db
from app.core.dependencies import CurrentUser, require_permission
from app.constants.permissions import ATTENDANCE_READ
from app.modules.reports import service
from app.utils.response import ok

router = APIRouter(prefix="/reports", tags=["Reports"])
DB = Annotated[AsyncSession, Depends(get_db)]


@router.get("/overview", response_model=dict, dependencies=[Depends(require_permission(ATTENDANCE_READ))])
async def reports_overview(current_user: CurrentUser, db: DB, academic_year_id: str | None = None, institution_id: str | None = None):
    target_institution_id = institution_id if current_user["is_superuser"] and institution_id else current_user["institution_id"]
    data = await service.build_overview(db, target_institution_id, academic_year_id)
    return ok(data=data)


@router.get("/overview/export.csv", response_model=None, dependencies=[Depends(require_permission(ATTENDANCE_READ))])
async def reports_overview_export(current_user: CurrentUser, db: DB, academic_year_id: str | None = None, institution_id: str | None = None):
    target_institution_id = institution_id if current_user["is_superuser"] and institution_id else current_user["institution_id"]
    data = await service.build_overview(db, target_institution_id, academic_year_id)
    stream = StringIO()
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(["section", "metric", "value"])
    for section in ["academics", "students", "teachers", "attendance", "fees", "exams", "library", "notifications", "audit"]:
        for key, value in (data.get(section) or {}).items():
            writer.writerow([section, key, value])
    writer.writerow([])
    writer.writerow(["coverage_module", "status", "details"])
    for item in data.get("coverage") or []:
        writer.writerow([item.get("module"), item.get("status"), item.get("details")])
    writer.writerow([])
    writer.writerow(["event_module", "action", "message", "created_at"])
    for item in data.get("recent_events") or []:
        writer.writerow([item.get("module"), item.get("action"), item.get("message"), item.get("created_at")])
    stream.seek(0)
    return StreamingResponse(
        iter([stream.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=reports_overview.csv"},
    )


def _download(content: bytes, filename: str, media_type: str):
    return StreamingResponse(
        iter([content]),
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/students/search", response_model=dict, dependencies=[Depends(require_permission(ATTENDANCE_READ))])
async def report_student_search(
    current_user: CurrentUser,
    db: DB,
    academic_year_id: str | None = None,
    course_id: str | None = None,
    branch_id: str | None = None,
    class_id: str | None = None,
    section_id: str | None = None,
    search: str | None = None,
):
    rows = await service.search_students(
        db,
        current_user["institution_id"],
        academic_year_id=academic_year_id,
        course_id=course_id,
        branch_id=branch_id,
        class_id=class_id,
        section_id=section_id,
        search=search,
    )
    return ok(data=rows)


@router.get("/students/{student_id}/complete", response_model=dict, dependencies=[Depends(require_permission(ATTENDANCE_READ))])
async def student_complete_report(student_id: str, current_user: CurrentUser, db: DB, academic_year_id: str | None = None):
    data = await service.student_complete_report(db, current_user["institution_id"], student_id, academic_year_id)
    return ok(data=data)


@router.get("/students/{student_id}/complete.pdf", response_model=None, dependencies=[Depends(require_permission(ATTENDANCE_READ))])
async def student_complete_report_pdf(student_id: str, current_user: CurrentUser, db: DB, academic_year_id: str | None = None):
    content = await service.student_complete_report_pdf(db, current_user["institution_id"], student_id, academic_year_id)
    return _download(content, "student_complete_report.pdf", "application/pdf")


@router.get("/students/{student_id}/report-card.pdf", response_model=None, dependencies=[Depends(require_permission(ATTENDANCE_READ))])
async def report_card_pdf(student_id: str, current_user: CurrentUser, db: DB, academic_year_id: str | None = None):
    content = await service.report_card_pdf(db, current_user["institution_id"], student_id, academic_year_id)
    return _download(content, "student_report_card.pdf", "application/pdf")


@router.get("/students/{student_id}/attendance-certificate.pdf", response_model=None, dependencies=[Depends(require_permission(ATTENDANCE_READ))])
async def attendance_certificate_pdf(student_id: str, current_user: CurrentUser, db: DB, academic_year_id: str | None = None):
    content = await service.attendance_certificate_pdf(db, current_user["institution_id"], student_id, academic_year_id)
    return _download(content, "attendance_certificate.pdf", "application/pdf")


@router.get("/fees/payments/{payment_id}/receipt.pdf", response_model=None, dependencies=[Depends(require_permission(ATTENDANCE_READ))])
async def fee_receipt_pdf(payment_id: str, current_user: CurrentUser, db: DB):
    content = await service.fee_receipt_pdf(db, current_user["institution_id"], payment_id)
    return _download(content, "fee_receipt.pdf", "application/pdf")


@router.get("/branch-report/export.csv", response_model=None, dependencies=[Depends(require_permission(ATTENDANCE_READ))])
async def branch_report_csv(current_user: CurrentUser, db: DB, academic_year_id: str | None = None, branch_id: str | None = None):
    content = await service.branch_report_csv(db, current_user["institution_id"], academic_year_id, branch_id)
    return _download(content, "branch_report.csv", "text/csv")


@router.get("/branch-report.pdf", response_model=None, dependencies=[Depends(require_permission(ATTENDANCE_READ))])
async def branch_report_pdf(current_user: CurrentUser, db: DB, academic_year_id: str | None = None, branch_id: str | None = None):
    content = await service.branch_report_pdf(db, current_user["institution_id"], academic_year_id, branch_id)
    return _download(content, "branch_report.pdf", "application/pdf")
