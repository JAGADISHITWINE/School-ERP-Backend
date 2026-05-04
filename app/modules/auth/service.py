from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_
from app.modules.users.model import User
from app.core.security import verify_password, create_access_token, create_refresh_token, decode_token
from app.core.exceptions import UnauthorizedError


async def login(db: AsyncSession, login_id: str, password: str) -> dict:
    result = await db.execute(
        select(User).where(
            or_(User.email == login_id, User.username == login_id),
            User.is_active == True,
        )
    )
    user = result.scalar_one_or_none()
    if not user or not verify_password(password, user.password_hash):
        raise UnauthorizedError("Invalid credentials")

    user.last_login = datetime.now(timezone.utc)
    await db.flush()

    return {
        "access_token": create_access_token(str(user.id), str(user.institution_id)),
        "refresh_token": create_refresh_token(str(user.id)),
        "token_type": "bearer",
    }


async def refresh(db: AsyncSession, refresh_token: str) -> dict:
    payload = decode_token(refresh_token)
    if not payload or payload.get("type") != "refresh":
        raise UnauthorizedError("Invalid or expired refresh token")

    result = await db.execute(
        select(User).where(User.id == payload["sub"], User.is_active == True)
    )
    user = result.scalar_one_or_none()
    if not user:
        raise UnauthorizedError("User not found")

    return {
        "access_token": create_access_token(str(user.id), str(user.institution_id)),
        "refresh_token": create_refresh_token(str(user.id)),
        "token_type": "bearer",
    }
