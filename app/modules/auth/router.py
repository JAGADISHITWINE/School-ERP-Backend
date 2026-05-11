from typing import Annotated
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.modules.auth import service
from app.modules.auth.schema import ChangePasswordRequest, LoginRequest, TokenResponse, RefreshRequest, ForgotPasswordRequest
from app.modules.users.model import User
from app.modules.roles.model import Menu, Permission, Role, RoleMenu, RolePermission, UserRole
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

    role_row = (
        await db.execute(
            select(Role.id, Role.slug, Role.name)
            .join(UserRole, UserRole.role_id == Role.id)
            .where(UserRole.user_id == user.id)
            .limit(1)
        )
    ).first()
    role_id, role_slug, role_name = role_row if role_row else (None, None, None)

    permissions = []
    menus = []
    if role_id:
        permission_rows = (
            await db.execute(
                select(Permission.code, Permission.module, Permission.action)
                .join(RolePermission, RolePermission.permission_id == Permission.id)
                .where(RolePermission.role_id == role_id)
                .order_by(Permission.module.asc(), Permission.action.asc())
            )
        ).all()
        permissions = sorted(
            {
                item
                for code, module, action in permission_rows
                for item in (code, f"{module}.{action}")
            }
        )

        menu_rows = (
            await db.execute(
                select(Menu)
                .join(RoleMenu, RoleMenu.menu_id == Menu.id)
                .where(RoleMenu.role_id == role_id, Menu.is_active == True)
                .order_by(Menu.order_no.asc(), Menu.label.asc())
            )
        ).scalars().all()
        menus = [
            {
                "id": str(menu.id),
                "label": menu.label,
                "path": menu.route or "",
                "icon": menu.icon or "",
                "order": menu.order_no,
                "roles": [role_slug] if role_slug else [],
            }
            for menu in menu_rows
        ]

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
            "permissions": permissions,
            "menus": menus,
        }
    )
