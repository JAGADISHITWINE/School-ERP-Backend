from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import delete, select, func
from app.modules.users.model import User
from app.modules.roles.model import Role, UserRole
from app.modules.users.schema import UserCreate, UserUpdate
from app.core.security import hash_password
from app.core.exceptions import NotFoundError, ConflictError, ValidationError


def _set_user_role_attrs(user: User, role_id=None, role_name=None) -> User:
    user.role_id = role_id
    user.role_name = role_name
    return user


async def _ensure_role_belongs_to_institution(
    db: AsyncSession, role_id: str, institution_id: str
) -> Role:
    role = (
        await db.execute(
            select(Role).where(
                Role.id == role_id,
                Role.institution_id == institution_id,
            )
        )
    ).scalar_one_or_none()
    if not role:
        raise ValidationError("Role not found for selected institution")
    return role


async def _attach_primary_role(db: AsyncSession, user: User) -> User:
    row = (
        await db.execute(
            select(Role.id, Role.name)
            .join(UserRole, UserRole.role_id == Role.id)
            .where(UserRole.user_id == user.id)
            .limit(1)
        )
    ).first()
    if not row:
        return _set_user_role_attrs(user)
    role_id, role_name = row
    return _set_user_role_attrs(user, role_id, role_name)


async def _attach_primary_roles(db: AsyncSession, users: list[User]) -> list[User]:
    if not users:
        return users

    user_ids = [u.id for u in users]
    rows = (
        await db.execute(
            select(UserRole.user_id, Role.id, Role.name)
            .join(Role, Role.id == UserRole.role_id)
            .where(UserRole.user_id.in_(user_ids))
        )
    ).all()

    role_by_user = {}
    for user_id, role_id, role_name in rows:
        role_by_user.setdefault(user_id, (role_id, role_name))

    for user in users:
        role_id, role_name = role_by_user.get(user.id, (None, None))
        _set_user_role_attrs(user, role_id, role_name)

    return users


async def create_user(db: AsyncSession, data: UserCreate) -> User:
    ex = (await db.execute(select(User).where(User.email == data.email))).scalar_one_or_none()
    if ex:
        raise ConflictError("Email already registered")
    ex2 = (await db.execute(select(User).where(User.username == data.username))).scalar_one_or_none()
    if ex2:
        raise ConflictError("Username already taken")
    role = None
    if data.role_id:
        role = await _ensure_role_belongs_to_institution(db, data.role_id, data.institution_id)

    user = User(
        institution_id=data.institution_id,
        email=data.email,
        username=data.username,
        password_hash=hash_password(data.password),
        full_name=data.full_name,
        phone=data.phone,
    )
    db.add(user)
    await db.flush()

    if data.role_id:
        db.add(UserRole(user_id=user.id, role_id=data.role_id))
        await db.flush()

    await db.refresh(user)
    if role:
        _set_user_role_attrs(user, role.id, role.name)
    else:
        _set_user_role_attrs(user)
    return user


async def list_users(db: AsyncSession, institution_id: str, offset: int, limit: int):
    q = select(User).where(User.institution_id == institution_id)
    total = (await db.execute(select(func.count()).select_from(q.subquery()))).scalar()
    result = await db.execute(q.offset(offset).limit(limit))
    users = result.scalars().all()
    return await _attach_primary_roles(db, users), total


async def get_user(db: AsyncSession, user_id: str) -> User:
    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if not user:
        raise NotFoundError("User not found")
    return await _attach_primary_role(db, user)


async def update_user(db: AsyncSession, user_id: str, data: UserUpdate) -> User:
    user = await get_user(db, user_id)
    incoming = data.model_dump(exclude_none=True)
    role_id = incoming.pop("role_id", None)

    for k, v in incoming.items():
        setattr(user, k, v)

    role = None
    if role_id:
        role = await _ensure_role_belongs_to_institution(db, role_id, user.institution_id)
        await db.execute(delete(UserRole).where(UserRole.user_id == user.id))
        db.add(UserRole(user_id=user.id, role_id=role_id))

    await db.flush()
    if role:
        _set_user_role_attrs(user, role.id, role.name)
    else:
        await _attach_primary_role(db, user)
    return user
