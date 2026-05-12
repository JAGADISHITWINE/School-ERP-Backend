import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field

from app.modules.teacher_content.model import AssessmentType, MaterialType


class ContentBase(BaseModel):
    academic_year_id: uuid.UUID
    branch_id: uuid.UUID
    class_id: uuid.UUID
    section_id: uuid.UUID
    subject_id: uuid.UUID
    title: str = Field(min_length=1, max_length=200)
    description: str | None = None


class MaterialCreate(ContentBase):
    material_type: MaterialType
    external_url: str | None = None


class AssessmentCreate(ContentBase):
    assessment_type: AssessmentType
    total_marks: int = Field(gt=0)
    due_date: date
    instructions: str | None = None


class AssignmentCreate(ContentBase):
    total_marks: int = Field(gt=0)
    due_date: date
    instructions: str | None = None


class SubmissionCreate(BaseModel):
    remarks: str | None = None


class ContentOut(BaseModel):
    id: uuid.UUID
    teacher_id: uuid.UUID
    academic_year_id: uuid.UUID
    academic_year_label: str | None = None
    branch_id: uuid.UUID
    branch_name: str | None = None
    class_id: uuid.UUID
    class_name: str | None = None
    section_id: uuid.UUID
    section_name: str | None = None
    subject_id: uuid.UUID
    subject_name: str | None = None
    title: str
    description: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class MaterialOut(ContentOut):
    material_type: MaterialType
    file_name: str | None = None
    file_url: str | None = None
    external_url: str | None = None


class AssessmentOut(ContentOut):
    assessment_type: AssessmentType
    total_marks: int
    due_date: date
    instructions: str | None = None
    attachment_name: str | None = None
    attachment_url: str | None = None


class AssignmentOut(ContentOut):
    total_marks: int
    due_date: date
    instructions: str | None = None
    attachment_name: str | None = None
    attachment_url: str | None = None
    submission_count: int = 0
    submitted: bool = False


class AssignmentSubmissionOut(BaseModel):
    id: uuid.UUID
    assignment_id: uuid.UUID
    student_id: uuid.UUID
    student_name: str | None = None
    roll_number: str | None = None
    remarks: str | None = None
    attachment_name: str | None = None
    attachment_url: str | None = None
    submitted_at: datetime
