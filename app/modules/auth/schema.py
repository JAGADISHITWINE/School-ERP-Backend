from pydantic import BaseModel, EmailStr, Field


class LoginRequest(BaseModel):
    login: str  # email or username
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class ForgotPasswordRequest(BaseModel):
    email: EmailStr

    password: str = Field(
        min_length=8,
        max_length=100,
    )
    confirm_password: str = Field(min_length=8, max_length=100)


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8, max_length=100)


class MeResponse(BaseModel):
    id: str
    email: str
    username: str
    full_name: str
    institution_id: str
    is_superuser: bool

    class Config:
        from_attributes = True
