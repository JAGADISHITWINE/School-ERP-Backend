from typing import Annotated
from fastapi import Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text
from app.core.security import decode_token
from app.core.exceptions import UnauthorizedError, ForbiddenError
from app.core.role_context import get_user_role_context
from app.db.session import get_db

bearer_scheme = HTTPBearer()


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(bearer_scheme)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    payload = decode_token(credentials.credentials)
    if not payload or payload.get("type") != "access":
        raise UnauthorizedError("Invalid or expired access token")

    user_id = payload.get("sub")
    # Lazy import to avoid circular deps
    from app.modules.users.model import User

    result = await db.execute(
        select(User).where(User.id == user_id, User.is_active == True)
    )
    user = result.scalar_one_or_none()
    if not user:
        raise UnauthorizedError("User not found or inactive")

    role_context = await get_user_role_context(db, str(user.id))

    return {
        "id": str(user.id),
        "institution_id": str(user.institution_id),
        "is_superuser": user.is_superuser,
        "email": user.email,
        **role_context,
    }


CurrentUser = Annotated[dict, Depends(get_current_user)]


def require_permission(permission_code: str):
    """
    Factory that returns a FastAPI dependency enforcing a single permission.
    Usage: Depends(require_permission("student_create"))
    """

    async def _checker(
        current_user: CurrentUser,
        db: Annotated[AsyncSession, Depends(get_db)],
    ):
        if current_user["is_superuser"]:
            return current_user

        # One query: user -> user_roles -> role_permissions -> permissions
        result = await db.execute(
            text(
                """
                SELECT 1 FROM user_roles ur
                JOIN role_permissions rp ON rp.role_id = ur.role_id
                JOIN permissions p ON p.id = rp.permission_id
                WHERE ur.user_id = :user_id
                  AND p.code = :code
                LIMIT 1
                """
            ),
            {"user_id": current_user["id"], "code": permission_code},
        )
        if not result.first():
            raise ForbiddenError(f"Missing permission: {permission_code}")

        return current_user

    return _checker
