from pydantic import BaseModel, EmailStr


class LoginRequest(BaseModel):
    login: str  # email or username
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class MeResponse(BaseModel):
    id: str
    email: str
    username: str
    full_name: str
    institution_id: str
    is_superuser: bool

    class Config:
        from_attributes = True
