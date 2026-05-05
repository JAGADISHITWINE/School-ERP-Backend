import uuid
from pydantic import BaseModel, EmailStr, field_validator
from datetime import datetime


class UserCreate(BaseModel):
    institution_id: uuid.UUID
    role_id: uuid.UUID | None = None
    email: EmailStr
    username: str
    password: str
    full_name: str
    phone: str | None = None


class UserUpdate(BaseModel):
    role_id: uuid.UUID | None = None
    full_name: str | None = None
    phone: str | None = None
    is_active: bool | None = None


class UserOut(BaseModel):
    id: uuid.UUID
    institution_id: uuid.UUID
    role_id: uuid.UUID | None = None
    role_name: str | None = None
    email: str
    username: str
    full_name: str
    phone: str | None
    is_active: bool
    is_superuser: bool
    created_at: datetime

    class Config:
        from_attributes = True
