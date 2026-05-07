import uuid
from pydantic import BaseModel, EmailStr
from datetime import date, datetime
from app.modules.students.model import StudentStatus


class StudentCreate(BaseModel):
    # User info
    institution_id: uuid.UUID
    email: EmailStr
    username: str
    password: str
    full_name: str
    phone: str | None = None
    # Student profile
    roll_number: str
    date_of_birth: date | None = None
    gender: str | None = None
    guardian_name: str | None = None
    guardian_phone: str | None = None
    # Initial academic record
    section_id: uuid.UUID
    branch_id: uuid.UUID
    academic_year_id: uuid.UUID


class StudentUpdate(BaseModel):
    full_name: str | None = None
    phone: str | None = None
    date_of_birth: date | None = None
    gender: str | None = None
    guardian_name: str | None = None
    guardian_phone: str | None = None


class AcademicRecordCreate(BaseModel):
    section_id: uuid.UUID
    branch_id: uuid.UUID
    academic_year_id: uuid.UUID


class AcademicRecordOut(BaseModel):
    id: uuid.UUID
    student_id: uuid.UUID
    section_id: uuid.UUID
    branch_id: uuid.UUID
    academic_year_id: uuid.UUID
    status: StudentStatus
    enrolled_at: datetime
    exited_at: datetime | None

    class Config:
        from_attributes = True


class AcademicRecordListItem(BaseModel):
    id: uuid.UUID
    student_id: uuid.UUID
    branch_id: uuid.UUID
    branch_name: str | None = None
    class_id: uuid.UUID | None = None
    class_name: str | None = None
    section_id: uuid.UUID
    section_name: str | None = None
    academic_year_id: uuid.UUID
    academic_year_label: str | None = None
    status: StudentStatus
    enrolled_at: datetime
    exited_at: datetime | None


class StudentOut(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    roll_number: str
    date_of_birth: date | None
    gender: str | None
    guardian_name: str | None
    guardian_phone: str | None
    full_name: str
    email: str
    role_slug: str | None = None
    current_branch_id: uuid.UUID | None = None
    current_branch_name: str | None = None
    current_class_id: uuid.UUID | None = None
    current_class_name: str | None = None
    current_section_id: uuid.UUID | None = None
    current_section_name: str | None = None
    current_academic_year_id: uuid.UUID | None = None
    current_academic_year_label: str | None = None
    current_status: StudentStatus | None = None
    created_at: datetime

    class Config:
        from_attributes = True
