import uuid
from pydantic import BaseModel
from datetime import date
from app.modules.attendance.model import AttendanceStatus, SessionStatus


class SessionCreate(BaseModel):
    section_id: uuid.UUID
    subject_id: uuid.UUID
    academic_year_id: uuid.UUID
    session_date: date


class AttendanceEntry(BaseModel):
    student_id: uuid.UUID
    status: AttendanceStatus
    remarks: str | None = None


class MarkAttendanceRequest(BaseModel):
    session_id: uuid.UUID
    records: list[AttendanceEntry]


class SessionOut(BaseModel):
    id: uuid.UUID
    section_id: uuid.UUID
    subject_id: uuid.UUID
    teacher_id: uuid.UUID
    academic_year_id: uuid.UUID
    session_date: date
    status: SessionStatus

    class Config:
        from_attributes = True


class AttendanceRecordOut(BaseModel):
    id: uuid.UUID
    session_id: uuid.UUID
    student_id: uuid.UUID
    status: AttendanceStatus
    remarks: str | None

    class Config:
        from_attributes = True
