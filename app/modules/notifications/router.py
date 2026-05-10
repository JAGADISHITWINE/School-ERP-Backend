from typing import Annotated
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.core.dependencies import CurrentUser, require_permission
from app.constants.permissions import NOTIFICATION_READ
from app.modules.notifications import service
from app.modules.notifications.schema import NotificationLogOut
from app.utils.pagination import PaginationParams
from app.utils.response import paginated

router = APIRouter(prefix="/notifications", tags=["Notifications"])
DB = Annotated[AsyncSession, Depends(get_db)]


@router.get("", response_model=dict, dependencies=[Depends(require_permission(NOTIFICATION_READ))])
async def list_notification_logs(current_user: CurrentUser, db: DB, pagination: Annotated[PaginationParams, Depends()]):
    institution_id = None if current_user["is_superuser"] else current_user["institution_id"]
    rows, total = await service.list_notifications(db, institution_id, pagination.offset, pagination.page_size)
    return paginated([NotificationLogOut.model_validate(row).model_dump() for row in rows], total, pagination.page, pagination.page_size)
