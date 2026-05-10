import uuid
from datetime import datetime
from pydantic import BaseModel
from app.modules.notifications.model import NotificationChannel, NotificationStatus


class NotificationLogOut(BaseModel):
    id: uuid.UUID
    institution_id: uuid.UUID | None
    student_id: uuid.UUID | None
    attendance_session_id: uuid.UUID | None
    channel: NotificationChannel
    recipient: str | None
    subject: str | None
    body: str | None
    status: NotificationStatus
    provider: str | None
    error_message: str | None
    dedupe_key: str | None
    created_at: datetime

    class Config:
        from_attributes = True
