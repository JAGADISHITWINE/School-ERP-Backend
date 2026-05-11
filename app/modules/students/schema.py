import uuid
from pydantic import BaseModel, EmailStr, field_validator
from datetime import date, datetime
from app.modules.students.model import StudentStatus


def clean_words(value: str | None) -> str | None:
    if value is None:
        return value
    cleaned = " ".join(value.strip().split())
    if not cleaned:
        return cleaned
    return cleaned[0].upper() + cleaned[1:]


def clean_token(value: str | None) -> str | None:
    if value is None:
        return value
    return " ".join(value.strip().split())


def validate_phone(value: str | None) -> str | None:
    value = clean_token(value)
    if not value:
        return value
    digits = "".join(ch for ch in value if ch.isdigit())
    if len(digits) < 10 or len(digits) > 15:
        raise ValueError("Phone number must contain 10 to 15 digits")
    return value


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
    guardian_email: EmailStr | None = None
    # Initial academic record
    section_id: uuid.UUID
    branch_id: uuid.UUID
    academic_year_id: uuid.UUID

    @field_validator("full_name", "guardian_name", "gender", mode="before")
    @classmethod
    def normalize_words(cls, value):
        return clean_words(value)

    @field_validator("username", "roll_number", mode="before")
    @classmethod
    def normalize_tokens(cls, value):
        return clean_token(value)

    @field_validator("phone", "guardian_phone", mode="before")
    @classmethod
    def normalize_phone(cls, value):
        return validate_phone(value)


class StudentUpdate(BaseModel):
    academic_year_id: uuid.UUID | None = None
    branch_id: uuid.UUID | None = None
    section_id: uuid.UUID | None = None
    full_name: str | None = None
    phone: str | None = None
    date_of_birth: date | None = None
    gender: str | None = None
    guardian_name: str | None = None
    guardian_phone: str | None = None
    guardian_email: EmailStr | None = None

    @field_validator("full_name", "guardian_name", "gender", mode="before")
    @classmethod
    def normalize_words(cls, value):
        return clean_words(value)

    @field_validator("phone", "guardian_phone", mode="before")
    @classmethod
    def normalize_phone(cls, value):
        return validate_phone(value)


class StudentStatusUpdate(BaseModel):
    status: StudentStatus


class StudentDocumentCreate(BaseModel):
    student_id: uuid.UUID
    document_type: str
    title: str
    file_name: str | None = None
    file_url: str | None = None
    status: str = "pending"
    remarks: str | None = None


class StudentDocumentUpdate(BaseModel):
    document_type: str | None = None
    title: str | None = None
    file_name: str | None = None
    file_url: str | None = None
    status: str | None = None
    remarks: str | None = None


class StudentDocumentOut(BaseModel):
    id: uuid.UUID
    student_id: uuid.UUID
    student_name: str | None = None
    roll_number: str | None = None
    document_type: str
    title: str
    file_name: str | None
    file_url: str | None
    status: str
    remarks: str | None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


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
    guardian_email: str | None
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
    updated_at: datetime

    class Config:
        from_attributes = True
