from typing import Annotated
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.modules.auth import service
from app.modules.auth.schema import ChangePasswordRequest, LoginRequest, TokenResponse, RefreshRequest, ForgotPasswordRequest
from app.modules.users.model import User
from app.modules.roles.model import Role, UserRole
from app.core.dependencies import CurrentUser
from app.utils.response import ok
from sqlalchemy import select
from app.modules.organizations.model import Organization
from app.modules.institutions.model import Institution
router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/login", response_model=dict, summary="Login with email/username + password")
async def login(payload: LoginRequest, db: Annotated[AsyncSession, Depends(get_db)]):
    tokens = await service.login(db, payload.login, payload.password)
    return ok(data=tokens, message="Login successful")


@router.post("/refresh", response_model=dict, summary="Refresh access token")
async def refresh(payload: RefreshRequest, db: Annotated[AsyncSession, Depends(get_db)]):
    tokens = await service.refresh(db, payload.refresh_token)
    return ok(data=tokens, message="Token refreshed")


@router.post("/reset-password", response_model=dict, summary="Reset password")
async def forgot_password(
    payload: ForgotPasswordRequest,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)]
):
    if str(payload.email).lower() != str(current_user["email"]).lower() and not current_user["is_superuser"]:
        from app.core.exceptions import ForbiddenError
        raise ForbiddenError("Cannot reset another user's password")
    result = await service.forgot_password(db, str(payload.email), payload.password)

    return ok(
        data=result,
        message="Password updated successfully",
    )


@router.post("/change-password", response_model=dict, summary="Change current user's password")
async def change_password(
    payload: ChangePasswordRequest,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    result = await service.change_password(db, current_user["id"], payload.current_password, payload.new_password)
    return ok(data=result, message="Password updated successfully")


@router.get("/me", response_model=dict, summary="Get current user profile")
async def me(
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)]
):
    result = await db.execute(
        select(User, Organization)
        .join(Institution, User.institution_id == Institution.id)
        .join(Organization, Institution.org_id == Organization.id)
        .where(User.id == current_user["id"])
    )

    row = result.first()
    user, organization = row

    role_row = (
        await db.execute(
            select(Role.slug, Role.name)
            .join(UserRole, UserRole.role_id == Role.id)
            .where(UserRole.user_id == user.id)
            .limit(1)
        )
    ).first()
    role_slug, role_name = role_row if role_row else (None, None)

    return ok(
        data={
            "id": str(user.id),
            "email": user.email,
            "username": user.username,
            "full_name": user.full_name,
            "institution_id": str(user.institution_id),
            "organization_id": str(organization.id),
            "organization_name": organization.name,
            "is_superuser": user.is_superuser,
            "role": role_slug,
            "role_name": role_name,
        }
    )
