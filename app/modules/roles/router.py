from typing import Annotated
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.modules.roles import service
from app.modules.roles.schema import RoleCreate, RoleUpdate, AssignPermissionsRequest, AssignRolesRequest, RoleOut, PermissionOut
from app.core.dependencies import CurrentUser, require_permission
from app.constants.permissions import ROLE_CREATE, ROLE_UPDATE, PERMISSION_MANAGE
from app.utils.response import ok, paginated
from app.utils.pagination import PaginationParams

router = APIRouter(prefix="/roles", tags=["Roles & Permissions"])


@router.get("/permissions", response_model=dict, summary="List all permission codes")
async def list_permissions(
    _: Annotated[dict, Depends(require_permission(ROLE_CREATE))],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    perms = await service.list_permissions(db)
    return ok(data=[PermissionOut.model_validate(p).model_dump() for p in perms])


@router.post("", response_model=dict, dependencies=[Depends(require_permission(ROLE_CREATE))])
async def create_role(payload: RoleCreate, db: Annotated[AsyncSession, Depends(get_db)]):
    role = await service.create_role(db, payload)
    return ok(data=RoleOut.model_validate(role).model_dump(), message="Role created")


@router.get("", response_model=dict)
async def list_roles(
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    pagination: Annotated[PaginationParams, Depends()],
):
    roles, total = await service.list_roles(
        db, current_user["institution_id"], pagination.offset, pagination.page_size
    )
    return paginated(
        [RoleOut.model_validate(r).model_dump() for r in roles],
        total, pagination.page, pagination.page_size
    )


@router.patch("/{role_id}", response_model=dict, dependencies=[Depends(require_permission(ROLE_UPDATE))])
async def update_role(role_id: str, payload: RoleUpdate, db: Annotated[AsyncSession, Depends(get_db)]):
    role = await service.update_role(db, role_id, payload)
    return ok(data=RoleOut.model_validate(role).model_dump(), message="Role updated")


@router.put("/{role_id}/permissions", response_model=dict, dependencies=[Depends(require_permission(PERMISSION_MANAGE))])
async def assign_permissions(role_id: str, payload: AssignPermissionsRequest, db: Annotated[AsyncSession, Depends(get_db)]):
    await service.assign_permissions(db, role_id, [str(p) for p in payload.permission_ids])
    return ok(message="Permissions assigned")


@router.put("/users/{user_id}/roles", response_model=dict, dependencies=[Depends(require_permission(ROLE_UPDATE))])
async def assign_roles_to_user(user_id: str, payload: AssignRolesRequest, db: Annotated[AsyncSession, Depends(get_db)]):
    await service.assign_roles_to_user(db, user_id, [str(r) for r in payload.role_ids])
    return ok(message="Roles assigned to user")
