import uuid
from pydantic import BaseModel, EmailStr, Field, model_validator
from datetime import date, time
from app.modules.teachers.model import TimetableDay


class TeacherCreate(BaseModel):
    user_id: uuid.UUID | None = None
    institution_id: uuid.UUID | None = None
    email: EmailStr | None = None
    username: str | None = None
    password: str | None = None
    full_name: str | None = None
    phone: str | None = None
    employee_code: str
    designation: str | None = None
    joined_at: date | None = None

    @model_validator(mode="after")
    def validate_teacher_source(self):
        if self.user_id:
            return self

        required_fields = {
            "institution_id": self.institution_id,
            "email": self.email,
            "username": self.username,
            "password": self.password,
            "full_name": self.full_name,
        }
        missing = [name for name, value in required_fields.items() if not value]
        if missing:
            missing_fields = ", ".join(missing)
            raise ValueError(
                f"Provide user_id for an existing user, or include: {missing_fields}"
            )
        return self


class TeacherUpdate(BaseModel):
    designation: str | None = None
    joined_at: date | None = None


class SubjectAssignRequest(BaseModel):
    subject_id: uuid.UUID
    section_id: uuid.UUID
    academic_year_id: uuid.UUID


class TeacherClassAssignRequest(BaseModel):
    class_id: uuid.UUID


class TeacherClassOut(BaseModel):
    id: uuid.UUID
    class_id: uuid.UUID
    class_name: str
    semester: int
    branch_id: uuid.UUID
    branch_name: str
    academic_year_id: uuid.UUID | None
    academic_year_label: str | None = None


class TeacherTimetableCreate(BaseModel):
    class_id: uuid.UUID
    section_id: uuid.UUID
    subject_id: uuid.UUID
    academic_year_id: uuid.UUID
    day_of_week: TimetableDay
    start_time: time
    end_time: time
    room_no: str | None = None
    version_no: int = 1
    is_active: bool = True


class TeacherTimetableUpdate(BaseModel):
    class_id: uuid.UUID | None = None
    section_id: uuid.UUID | None = None
    subject_id: uuid.UUID | None = None
    academic_year_id: uuid.UUID | None = None
    day_of_week: TimetableDay | None = None
    start_time: time | None = None
    end_time: time | None = None
    room_no: str | None = None
    version_no: int | None = None
    is_active: bool | None = None


class TeacherTimetableOut(BaseModel):
    id: uuid.UUID
    teacher_id: uuid.UUID
    class_id: uuid.UUID
    class_name: str
    section_id: uuid.UUID
    section_name: str
    subject_id: uuid.UUID
    subject_name: str
    branch_id: uuid.UUID
    branch_name: str
    academic_year_id: uuid.UUID
    academic_year_label: str | None = None
    day_of_week: TimetableDay
    start_time: time
    end_time: time
    room_no: str | None = None
    version_no: int = 1
    is_active: bool = True
    session_id: uuid.UUID | None = None
    session_status: str | None = None
    session_date: date | None = None


class TeacherCandidateOut(BaseModel):
    user_id: uuid.UUID
    institution_id: uuid.UUID
    full_name: str
    email: str
    username: str
    phone: str | None = None


class TeacherOut(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    employee_code: str
    designation: str | None
    joined_at: date | None
    full_name: str
    email: str
    username: str
    phone: str | None = None
    assigned_classes: list[TeacherClassOut] = Field(default_factory=list)

    class Config:
        from_attributes = True
