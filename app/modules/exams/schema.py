import uuid
from pydantic import BaseModel
from datetime import date
from app.modules.exams.model import ExamWorkflow


class ExamCreate(BaseModel):
    institution_id: uuid.UUID
    academic_year_id: uuid.UUID
    name: str
    exam_type: str


class ExamUpdate(BaseModel):
    name: str | None = None
    exam_type: str | None = None


class ExamSubjectCreate(BaseModel):
    subject_id: uuid.UUID
    max_marks: int
    pass_marks: int
    exam_date: date | None = None


class ExamOut(BaseModel):
    id: uuid.UUID
    institution_id: uuid.UUID
    academic_year_id: uuid.UUID
    name: str
    exam_type: str
    workflow_status: ExamWorkflow

    class Config:
        from_attributes = True


class MarkEntry(BaseModel):
    student_id: uuid.UUID
    marks_obtained: float | None = None
    is_absent: bool = False


class MarksUploadRequest(BaseModel):
    exam_subject_id: uuid.UUID
    entries: list[MarkEntry]


class MarkOut(BaseModel):
    id: uuid.UUID
    exam_subject_id: uuid.UUID
    student_id: uuid.UUID
    marks_obtained: float | None
    is_absent: bool
    is_locked: bool

    class Config:
        from_attributes = True
