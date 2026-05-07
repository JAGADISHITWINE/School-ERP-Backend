import uuid
from pydantic import BaseModel
from datetime import date
from app.modules.attendance.model import AttendanceStatus, SessionStatus
from app.modules.teachers.model import TimetableDay


class SessionCreate(BaseModel):
    teacher_id: uuid.UUID | None = None
    timetable_id: uuid.UUID | None = None
    section_id: uuid.UUID | None = None
    subject_id: uuid.UUID | None = None
    academic_year_id: uuid.UUID | None = None
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
    timetable_id: uuid.UUID | None = None
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


class AttendanceStudentOut(BaseModel):
    student_id: uuid.UUID
    roll_number: str
    full_name: str
    status: AttendanceStatus | None = None
    remarks: str | None = None


class AttendanceContextItem(BaseModel):
    timetable_id: uuid.UUID
    teacher_id: uuid.UUID
    class_id: uuid.UUID
    class_name: str
    section_id: uuid.UUID
    section_name: str
    subject_id: uuid.UUID
    subject_name: str
    academic_year_id: uuid.UUID
    academic_year_label: str | None = None
    branch_name: str
    day_of_week: TimetableDay
    start_time: str
    end_time: str
    room_no: str | None = None
    session_id: uuid.UUID | None = None
    session_status: str | None = None
    session_date: date | None = None
