from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, insert, delete, func
from app.modules.roles.model import Role, UserRole, RolePermission, Permission
from app.modules.roles.schema import RoleCreate, RoleUpdate
from app.core.exceptions import NotFoundError, ConflictError


async def create_role(db: AsyncSession, data: RoleCreate) -> Role:
    existing = await db.execute(select(Role).where(Role.slug == data.slug))
    if existing.scalar_one_or_none():
        raise ConflictError(f"Role slug '{data.slug}' already exists")
    role = Role(**data.model_dump())
    db.add(role)
    await db.flush()
    await db.refresh(role)
    return role


async def list_roles(db: AsyncSession, institution_id: str, offset: int, limit: int):
    total_q = await db.execute(select(func.count()).select_from(Role).where(Role.institution_id == institution_id))
    total = total_q.scalar()
    result = await db.execute(
        select(Role).where(Role.institution_id == institution_id).offset(offset).limit(limit)
    )
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


async def assign_permissions(db: AsyncSession, role_id: str, permission_ids: list[str]):
    await db.execute(delete(RolePermission).where(RolePermission.role_id == role_id))
    if permission_ids:
        await db.execute(
            insert(RolePermission),
            [{"role_id": role_id, "permission_id": pid} for pid in permission_ids],
        )
    await db.flush()


async def assign_roles_to_user(db: AsyncSession, user_id: str, role_ids: list[str]):
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
