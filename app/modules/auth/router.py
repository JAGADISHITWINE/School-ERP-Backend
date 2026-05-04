from typing import Annotated
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.modules.auth import service
from app.modules.auth.schema import LoginRequest, TokenResponse, RefreshRequest
from app.modules.users.model import User
from app.core.dependencies import CurrentUser
from app.utils.response import ok
from sqlalchemy import select

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/login", response_model=dict, summary="Login with email/username + password")
async def login(payload: LoginRequest, db: Annotated[AsyncSession, Depends(get_db)]):
    tokens = await service.login(db, payload.login, payload.password)
    return ok(data=tokens, message="Login successful")


@router.post("/refresh", response_model=dict, summary="Refresh access token")
async def refresh(payload: RefreshRequest, db: Annotated[AsyncSession, Depends(get_db)]):
    tokens = await service.refresh(db, payload.refresh_token)
    return ok(data=tokens, message="Token refreshed")


@router.get("/me", response_model=dict, summary="Get current user profile")
async def me(current_user: CurrentUser, db: Annotated[AsyncSession, Depends(get_db)]):
    result = await db.execute(select(User).where(User.id == current_user["id"]))
    user = result.scalar_one()
    return ok(
        data={
            "id": str(user.id),
            "email": user.email,
            "username": user.username,
            "full_name": user.full_name,
            "institution_id": str(user.institution_id),
            "is_superuser": user.is_superuser,
        }
    )
