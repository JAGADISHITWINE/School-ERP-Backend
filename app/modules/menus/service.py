from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text, insert, delete
from app.modules.roles.model import Menu, RoleMenu, UserRole
from app.modules.menus.schema import MenuCreate, MenuUpdate, MenuNode
from app.core.exceptions import NotFoundError


def _build_tree(menus: list[Menu]) -> list[dict]:
    """Build nested menu tree from flat list."""
    menu_map = {str(m.id): {
        "id": str(m.id),
        "parent_id": str(m.parent_id) if m.parent_id else None,
        "label": m.label,
        "route": m.route,
        "icon": m.icon,
        "order_no": m.order_no,
        "children": [],
    } for m in menus}

    roots = []
    for node in menu_map.values():
        pid = node["parent_id"]
        if pid and pid in menu_map:
            menu_map[pid]["children"].append(node)
        else:
            roots.append(node)

    return sorted(roots, key=lambda x: x["order_no"])


async def get_user_menus(db: AsyncSession, user_id: str, is_superuser: bool) -> list[dict]:
    if is_superuser:
        result = await db.execute(
            select(Menu).where(Menu.is_active == True).order_by(Menu.order_no)
        )
        return _build_tree(result.scalars().all())

    result = await db.execute(
        text(
            """
            SELECT DISTINCT m.* FROM menus m
            JOIN role_menus rm ON rm.menu_id = m.id
            JOIN user_roles ur ON ur.role_id = rm.role_id
            WHERE ur.user_id = :user_id AND m.is_active = true
            ORDER BY m.order_no
            """
        ),
        {"user_id": user_id},
    )
    rows = result.mappings().all()
    # Re-fetch as ORM objects to use the model
    menu_ids = [r["id"] for r in rows]
    if not menu_ids:
        return []
    orm_result = await db.execute(
        select(Menu).where(Menu.id.in_(menu_ids)).order_by(Menu.order_no)
    )
    return _build_tree(orm_result.scalars().all())


async def create_menu(db: AsyncSession, data: MenuCreate) -> Menu:
    menu = Menu(**data.model_dump())
    db.add(menu)
    await db.flush()
    await db.refresh(menu)
    return menu


async def update_menu(db: AsyncSession, menu_id: str, data: MenuUpdate) -> Menu:
    result = await db.execute(select(Menu).where(Menu.id == menu_id))
    menu = result.scalar_one_or_none()
    if not menu:
        raise NotFoundError("Menu not found")
    for k, v in data.model_dump(exclude_none=True).items():
        setattr(menu, k, v)
    await db.flush()
    return menu


async def assign_menus_to_role(db: AsyncSession, role_id: str, menu_ids: list[str]):
    await db.execute(delete(RoleMenu).where(RoleMenu.role_id == role_id))
    if menu_ids:
        await db.execute(
            insert(RoleMenu),
            [{"role_id": role_id, "menu_id": mid} for mid in menu_ids],
        )
    await db.flush()
