import uuid
from pydantic import BaseModel
from datetime import datetime


class OrgCreate(BaseModel):
    name: str
    slug: str
    logo_url: str | None = None


class OrgUpdate(BaseModel):
    name: str | None = None
    slug: str | None = None
    logo_url: str | None = None
    is_active: bool | None = None


class OrgOut(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    logo_url: str | None
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class InstitutionCreate(BaseModel):
    org_id: uuid.UUID
    name: str
    code: str
    address: str | None = None


class InstitutionUpdate(BaseModel):
    name: str | None = None
    code: str | None = None
    address: str | None = None
    is_active: bool | None = None


class InstitutionOut(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    name: str
    code: str
    address: str | None
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True
