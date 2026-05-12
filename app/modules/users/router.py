from typing import Annotated
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.modules.users import service
from app.modules.users.schema import UserCreate, UserUpdate, UserOut
from app.core.dependencies import CurrentUser, require_permission
from app.constants.permissions import USER_CREATE, USER_READ, USER_UPDATE, USER_DELETE
from app.utils.response import ok, paginated
from app.utils.pagination import PaginationParams

router = APIRouter(prefix="/users", tags=["Users"])
DB = Annotated[AsyncSession, Depends(get_db)]


@router.post("", response_model=dict, dependencies=[Depends(require_permission(USER_CREATE))])
async def create_user(payload: UserCreate, current_user: CurrentUser, db: DB):
    user = await service.create_user(db, payload, current_user)
    data = UserOut.model_validate(user).model_dump()
    data["credentials_dispatched"] = bool(getattr(user, "credentials_dispatched", False))
    if not data["credentials_dispatched"]:
        data["generated_password"] = getattr(user, "generated_password", None)
    return ok(data=data, message="User created")


@router.get("", response_model=dict, dependencies=[Depends(require_permission(USER_READ))])
async def list_users(
    current_user: CurrentUser, db: DB,
    pagination: Annotated[PaginationParams, Depends()],
    search: str | None = None,
):
    users, total = await service.list_users(
        db,
        current_user["institution_id"],
        pagination.offset,
        pagination.page_size,
        current_user,
        search=search,
    )
    return paginated(
        [UserOut.model_validate(u).model_dump() for u in users],
        total, pagination.page, pagination.page_size,
    )


@router.get("/{user_id}", response_model=dict, dependencies=[Depends(require_permission(USER_READ))])
async def get_user(user_id: str, current_user: CurrentUser, db: DB):
    user = await service.get_user(db, user_id, current_user)
    return ok(data=UserOut.model_validate(user).model_dump())


@router.patch("/{user_id}", response_model=dict, dependencies=[Depends(require_permission(USER_UPDATE))])
async def update_user(user_id: str, payload: UserUpdate, current_user: CurrentUser, db: DB):
    user = await service.update_user(db, user_id, payload, current_user)
    return ok(data=UserOut.model_validate(user).model_dump(), message="User updated")


@router.delete("/{user_id}", response_model=dict, dependencies=[Depends(require_permission(USER_DELETE))])
async def delete_user(user_id: str, current_user: CurrentUser, db: DB):
    await service.delete_user(db, user_id, current_user)
    return ok(message="User deleted")
