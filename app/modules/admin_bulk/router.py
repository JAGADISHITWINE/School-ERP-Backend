from typing import Annotated

from fastapi import APIRouter, Depends, File, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants.permissions import ADMIN_BULK_MANAGE
from app.core.dependencies import CurrentUser, require_permission
from app.db.session import get_db
from app.modules.admin_bulk import service
from app.utils.response import ok

router = APIRouter(prefix="/admin-bulk", tags=["Admin Bulk Tools"])
DB = Annotated[AsyncSession, Depends(get_db)]


def _download(content: bytes, filename: str):
    return StreamingResponse(
        iter([content]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/resources", response_model=dict, dependencies=[Depends(require_permission(ADMIN_BULK_MANAGE))])
async def resources():
    return ok(data=[{"key": key, "headers": spec["headers"]} for key, spec in service.SPECS.items()])


@router.get("/templates/{resource}.csv", response_model=None, dependencies=[Depends(require_permission(ADMIN_BULK_MANAGE))])
async def template(resource: str):
    return _download(service.template_bytes(resource), f"{resource}-template.csv")


@router.get("/exports/{resource}.csv", response_model=None, dependencies=[Depends(require_permission(ADMIN_BULK_MANAGE))])
async def export(resource: str, current_user: CurrentUser, db: DB):
    content = await service.export_rows(db, current_user["institution_id"], resource)
    return _download(content, f"{resource}-export.csv")


@router.post("/imports/{resource}", response_model=dict, dependencies=[Depends(require_permission(ADMIN_BULK_MANAGE))])
async def import_file(resource: str, current_user: CurrentUser, db: DB, file: UploadFile = File(...)):
    content = await file.read()
    rows = service.parse_upload(file.filename or "upload.csv", content)
    result = await service.import_rows(db, current_user["institution_id"], resource, rows)
    await db.commit()
    return ok(data=result, message="Import completed")

