import uuid
from pydantic import BaseModel, EmailStr
from datetime import date


class TeacherCreate(BaseModel):
    institution_id: uuid.UUID
    email: EmailStr
    username: str
    password: str
    full_name: str
    phone: str | None = None
    employee_code: str
    designation: str | None = None
    joined_at: date | None = None


class TeacherUpdate(BaseModel):
    designation: str | None = None
    joined_at: date | None = None


class SubjectAssignRequest(BaseModel):
    subject_id: uuid.UUID
    section_id: uuid.UUID
    academic_year_id: uuid.UUID


class TeacherOut(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    employee_code: str
    designation: str | None
    joined_at: date | None
    full_name: str
    email: str

    class Config:
        from_attributes = True
