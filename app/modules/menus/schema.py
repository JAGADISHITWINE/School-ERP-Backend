import uuid
from pydantic import BaseModel


class MenuCreate(BaseModel):
    parent_id: uuid.UUID | None = None
    label: str
    route: str | None = None
    icon: str | None = None
    order_no: int = 0


class MenuUpdate(BaseModel):
    label: str | None = None
    route: str | None = None
    icon: str | None = None
    order_no: int | None = None
    is_active: bool | None = None


class MenuOut(BaseModel):
    id: uuid.UUID
    parent_id: uuid.UUID | None
    label: str
    route: str | None
    icon: str | None
    order_no: int
    is_active: bool

    class Config:
        from_attributes = True


class MenuNode(BaseModel):
    id: uuid.UUID
    parent_id: uuid.UUID | None
    label: str
    route: str | None
    icon: str | None
    order_no: int
    children: list["MenuNode"] = []

    class Config:
        from_attributes = True


MenuNode.model_rebuild()  # required for self-referential model
