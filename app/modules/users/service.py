from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.modules.users.model import User
from app.modules.users.schema import UserCreate, UserUpdate
from app.core.security import hash_password
from app.core.exceptions import NotFoundError, ConflictError


async def create_user(db: AsyncSession, data: UserCreate) -> User:
    ex = (await db.execute(select(User).where(User.email == data.email))).scalar_one_or_none()
    if ex:
        raise ConflictError("Email already registered")
    ex2 = (await db.execute(select(User).where(User.username == data.username))).scalar_one_or_none()
    if ex2:
        raise ConflictError("Username already taken")

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
    await db.refresh(user)
    return user


async def list_users(db: AsyncSession, institution_id: str, offset: int, limit: int):
    q = select(User).where(User.institution_id == institution_id)
    total = (await db.execute(select(func.count()).select_from(q.subquery()))).scalar()
    result = await db.execute(q.offset(offset).limit(limit))
    return result.scalars().all(), total


async def get_user(db: AsyncSession, user_id: str) -> User:
    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if not user:
        raise NotFoundError("User not found")
    return user


async def update_user(db: AsyncSession, user_id: str, data: UserUpdate) -> User:
    user = await get_user(db, user_id)
    for k, v in data.model_dump(exclude_none=True).items():
        setattr(user, k, v)
    await db.flush()
    return user
