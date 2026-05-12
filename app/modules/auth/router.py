from typing import Annotated
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.modules.auth import service
from app.modules.auth.schema import ChangePasswordRequest, LoginRequest, TokenResponse, RefreshRequest, ForgotPasswordRequest
from app.modules.users.model import User
from app.core.role_context import get_user_role_context
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
    db: Annotated[AsyncSession, Depends(get_db)]
):
    if payload.password != payload.confirm_password:
        from app.core.exceptions import BusinessRuleError
        raise BusinessRuleError("Passwords do not match")
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

    role_context = await get_user_role_context(db, str(user.id))

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
            "role": role_context["role"],
            "roles": role_context["roles"],
            "role_name": role_context["role_names"][0] if role_context["role_names"] else None,
            "role_names": role_context["role_names"],
            "permissions": role_context["permissions"],
            "menus": role_context["menus"],
        }
    )
