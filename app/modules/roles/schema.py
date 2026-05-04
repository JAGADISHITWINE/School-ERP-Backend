import uuid
from pydantic import BaseModel
from datetime import datetime


class PermissionOut(BaseModel):
    id: uuid.UUID
    code: str
    module: str
    action: str
    description: str | None

    class Config:
        from_attributes = True


class RoleCreate(BaseModel):
    institution_id: uuid.UUID
    name: str
    slug: str
    description: str | None = None


class RoleUpdate(BaseModel):
    name: str | None = None
    description: str | None = None


class RoleOut(BaseModel):
    id: uuid.UUID
    institution_id: uuid.UUID
    name: str
    slug: str
    description: str | None
    is_system: bool
    created_at: datetime

    class Config:
        from_attributes = True


class AssignPermissionsRequest(BaseModel):
    permission_ids: list[uuid.UUID]


class AssignMenusRequest(BaseModel):
    menu_ids: list[uuid.UUID]


class AssignRolesRequest(BaseModel):
    role_ids: list[uuid.UUID]
