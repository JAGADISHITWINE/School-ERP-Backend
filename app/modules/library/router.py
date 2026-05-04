from typing import Annotated
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.modules.library import service
from app.modules.library.schema import (
    BookCreate, BookUpdate, BookOut,
    IssueBookRequest, ReturnBookRequest, BookIssueOut,
)
from app.core.dependencies import require_permission
from app.constants.permissions import LIBRARY_MANAGE, LIBRARY_ISSUE
from app.utils.response import ok, paginated
from app.utils.pagination import PaginationParams

router = APIRouter(prefix="/library", tags=["Library"])
DB = Annotated[AsyncSession, Depends(get_db)]


@router.post("/books", response_model=dict, dependencies=[Depends(require_permission(LIBRARY_MANAGE))])
async def create_book(payload: BookCreate, db: DB):
    book = await service.create_book(db, payload)
    return ok(data=BookOut.model_validate(book).model_dump(), message="Book added")


@router.get("/books", response_model=dict)
async def list_books(
    institution_id: str, db: DB,
    pagination: Annotated[PaginationParams, Depends()],
):
    books, total = await service.list_books(db, institution_id, pagination.offset, pagination.page_size)
    return paginated(
        [BookOut.model_validate(b).model_dump() for b in books],
        total, pagination.page, pagination.page_size,
    )


@router.patch("/books/{book_id}", response_model=dict, dependencies=[Depends(require_permission(LIBRARY_MANAGE))])
async def update_book(book_id: str, payload: BookUpdate, db: DB):
    book = await service.update_book(db, book_id, payload)
    return ok(data=BookOut.model_validate(book).model_dump())


@router.post("/issue", response_model=dict, dependencies=[Depends(require_permission(LIBRARY_ISSUE))])
async def issue_book(payload: IssueBookRequest, db: DB):
    issue = await service.issue_book(db, payload)
    return ok(data=BookIssueOut.model_validate(issue).model_dump(), message="Book issued")


@router.post("/return", response_model=dict, dependencies=[Depends(require_permission(LIBRARY_ISSUE))])
async def return_book(payload: ReturnBookRequest, db: DB):
    issue = await service.return_book(db, payload)
    return ok(
        data=BookIssueOut.model_validate(issue).model_dump(),
        message=f"Book returned. Fine: ₹{issue.fine_amount:.2f}",
    )


@router.get("/issues", response_model=dict)
async def list_issues(
    db: DB,
    pagination: Annotated[PaginationParams, Depends()],
    student_id: str | None = None,
):
    issues, total = await service.list_issues(db, student_id, pagination.offset, pagination.page_size)
    return paginated(
        [BookIssueOut.model_validate(i).model_dump() for i in issues],
        total, pagination.page, pagination.page_size,
    )
