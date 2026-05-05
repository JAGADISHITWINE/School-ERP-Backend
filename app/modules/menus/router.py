from typing import Annotated
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.modules.menus import service
from app.modules.menus.schema import MenuCreate, MenuUpdate, MenuOut
from app.core.dependencies import CurrentUser, require_permission
from app.constants.permissions import MENU_MANAGE, PERMISSION_MANAGE
from app.utils.response import ok

router = APIRouter(prefix="/menus", tags=["Menus"])


@router.get("", response_model=dict, dependencies=[Depends(require_permission(PERMISSION_MANAGE))])
async def list_menus(db: Annotated[AsyncSession, Depends(get_db)]):
    menus = await service.list_menus(db)
    return ok(data=[MenuOut.model_validate(m).model_dump() for m in menus])


@router.get("/me", response_model=dict, summary="Get role-based menu tree for current user")
async def my_menus(current_user: CurrentUser, db: Annotated[AsyncSession, Depends(get_db)]):
    tree = await service.get_user_menus(db, current_user["id"], current_user["is_superuser"])
    return ok(data=tree)


@router.post("", response_model=dict, dependencies=[Depends(require_permission(MENU_MANAGE))])
async def create_menu(payload: MenuCreate, db: Annotated[AsyncSession, Depends(get_db)]):
    menu = await service.create_menu(db, payload)
    return ok(data={"id": str(menu.id)}, message="Menu created")


@router.patch("/{menu_id}", response_model=dict, dependencies=[Depends(require_permission(MENU_MANAGE))])
async def update_menu(menu_id: str, payload: MenuUpdate, db: Annotated[AsyncSession, Depends(get_db)]):
    menu = await service.update_menu(db, menu_id, payload)
    return ok(data={"id": str(menu.id)}, message="Menu updated")
