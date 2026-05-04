import uuid
from pydantic import BaseModel
from datetime import date, datetime
from app.modules.library.model import IssueStatus


class BookCreate(BaseModel):
    institution_id: uuid.UUID
    isbn: str
    title: str
    author: str
    publisher: str | None = None
    total_copies: int = 1


class BookUpdate(BaseModel):
    title: str | None = None
    author: str | None = None
    total_copies: int | None = None


class BookOut(BaseModel):
    id: uuid.UUID
    isbn: str
    title: str
    author: str
    publisher: str | None
    total_copies: int
    available_copies: int

    class Config:
        from_attributes = True


class IssueBookRequest(BaseModel):
    book_id: uuid.UUID
    student_id: uuid.UUID
    due_date: date


class ReturnBookRequest(BaseModel):
    issue_id: uuid.UUID
    fine_per_day: float = 1.0


class BookIssueOut(BaseModel):
    id: uuid.UUID
    book_id: uuid.UUID
    student_id: uuid.UUID
    issued_on: date
    due_date: date
    returned_on: date | None
    fine_amount: float
    status: IssueStatus

    class Config:
        from_attributes = True
