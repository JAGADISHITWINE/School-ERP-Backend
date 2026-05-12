from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, insert, delete, func
from app.modules.roles.model import Role, UserRole, RolePermission, Permission, RoleMenu, Menu
from app.modules.roles.schema import RoleCreate, RoleUpdate
from app.core.exceptions import NotFoundError, ConflictError, ValidationError, ForbiddenError


SUPERADMIN_SLUGS = {"superadmin", "super_admin"}
ADMIN_ALLOWED_ROLE_SLUGS = {
    "admin",
    "administrator",
    "college admin",
    "school admin",
    "institute admin",
    "institution admin",
    "hod",
    "head_of_department",
    "head of department",
    "teacher",
    "teachers",
    "faculty",
    "lecturer",
    "student",
    "students",
    "parent",
    "guardian",
    "principal",
    "principle",
}


async def _actor_can_manage_superadmin(db: AsyncSession, actor: dict) -> bool:
    if actor.get("is_superuser"):
        return True
    row = (
        await db.execute(
            select(Role.id)
            .join(UserRole, UserRole.role_id == Role.id)
            .where(UserRole.user_id == actor["id"], func.lower(Role.slug).in_(SUPERADMIN_SLUGS))
            .limit(1)
        )
    ).first()
    return row is not None


async def get_role_for_institution(db: AsyncSession, role_id: str, institution_id: str) -> Role:
    role = (
        await db.execute(
            select(Role).where(Role.id == role_id, Role.institution_id == institution_id)
        )
    ).scalar_one_or_none()
    if not role:
        raise NotFoundError("Role not found")
    return role


async def create_role(db: AsyncSession, data: RoleCreate) -> Role:
    existing = await db.execute(select(Role).where(Role.slug == data.slug))
    if existing.scalar_one_or_none():
        raise ConflictError(f"Role slug '{data.slug}' already exists")
    role = Role(**data.model_dump())
    db.add(role)
    await db.flush()
    await db.refresh(role)
    return role


async def list_roles(db: AsyncSession, institution_id: str, offset: int, limit: int, actor: dict | None = None):
    q = select(Role).where(Role.institution_id == institution_id)
    if actor and not await _actor_can_manage_superadmin(db, actor):
        q = q.where(
            func.lower(Role.slug).in_(ADMIN_ALLOWED_ROLE_SLUGS)
            | func.lower(Role.name).in_(ADMIN_ALLOWED_ROLE_SLUGS)
        )
    total_q = await db.execute(select(func.count()).select_from(q.subquery()))
    total = total_q.scalar()
    result = await db.execute(q.order_by(Role.name.asc()).offset(offset).limit(limit))
    return result.scalars().all(), total


async def update_role(db: AsyncSession, role_id: str, data: RoleUpdate) -> Role:
    result = await db.execute(select(Role).where(Role.id == role_id))
    role = result.scalar_one_or_none()
    if not role:
        raise NotFoundError("Role not found")
    for k, v in data.model_dump(exclude_none=True).items():
        setattr(role, k, v)
    await db.flush()
    return role


async def get_role_access(db: AsyncSession, role_id: str, institution_id: str):
    role = await get_role_for_institution(db, role_id, institution_id)
    permission_ids = (
        await db.execute(
            select(RolePermission.permission_id).where(RolePermission.role_id == role.id)
        )
    ).scalars().all()
    menu_ids = (
        await db.execute(select(RoleMenu.menu_id).where(RoleMenu.role_id == role.id))
    ).scalars().all()
    return role, permission_ids, menu_ids


async def assign_permissions(
    db: AsyncSession, role_id: str, institution_id: str, permission_ids: list[str]
):
    role = await get_role_for_institution(db, role_id, institution_id)
    if permission_ids:
        existing = (
            await db.execute(select(Permission.id).where(Permission.id.in_(permission_ids)))
        ).scalars().all()
        if len(set(existing)) != len(set(permission_ids)):
            raise ValidationError("One or more permissions are invalid")

    await db.execute(delete(RolePermission).where(RolePermission.role_id == role_id))
    if permission_ids:
        await db.execute(
            insert(RolePermission),
            [{"role_id": role.id, "permission_id": pid} for pid in permission_ids],
        )
    await db.flush()


async def assign_menus(
    db: AsyncSession, role_id: str, institution_id: str, menu_ids: list[str]
):
    role = await get_role_for_institution(db, role_id, institution_id)
    if menu_ids:
        existing = (
            await db.execute(select(Menu.id).where(Menu.id.in_(menu_ids)))
        ).scalars().all()
        if len(set(existing)) != len(set(menu_ids)):
            raise ValidationError("One or more menus are invalid")

    await db.execute(delete(RoleMenu).where(RoleMenu.role_id == role.id))
    if menu_ids:
        await db.execute(
            insert(RoleMenu),
            [{"role_id": role.id, "menu_id": mid} for mid in menu_ids],
        )
    await db.flush()


async def assign_roles_to_user(db: AsyncSession, user_id: str, role_ids: list[str], actor: dict | None = None):
    if actor and not await _actor_can_manage_superadmin(db, actor):
        target_superadmin = (
            await db.execute(
                select(Role.id)
                .join(UserRole, UserRole.role_id == Role.id)
                .where(UserRole.user_id == user_id, func.lower(Role.slug).in_(SUPERADMIN_SLUGS))
                .limit(1)
            )
        ).first()
        if target_superadmin:
            raise ForbiddenError("Admin cannot assign roles to Superadmin users")
        incoming_superadmin = (
            await db.execute(select(Role.id).where(Role.id.in_(role_ids), func.lower(Role.slug).in_(SUPERADMIN_SLUGS)))
        ).first()
        if incoming_superadmin:
            raise ForbiddenError("Admin cannot assign Superadmin role")
    await db.execute(delete(UserRole).where(UserRole.user_id == user_id))
    if role_ids:
        await db.execute(
            insert(UserRole),
            [{"user_id": user_id, "role_id": rid} for rid in role_ids],
        )
    await db.flush()


async def list_permissions(db: AsyncSession):
    result = await db.execute(select(Permission).order_by(Permission.module, Permission.action))
    return result.scalars().all()
