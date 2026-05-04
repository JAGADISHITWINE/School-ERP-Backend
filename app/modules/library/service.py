from datetime import date
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.modules.library.model import Book, BookIssue, IssueStatus
from app.modules.library.schema import BookCreate, BookUpdate, IssueBookRequest, ReturnBookRequest
from app.core.exceptions import NotFoundError, BusinessRuleError


async def create_book(db: AsyncSession, data: BookCreate) -> Book:
    obj = Book(**data.model_dump())
    db.add(obj); await db.flush(); await db.refresh(obj)
    return obj


async def list_books(db: AsyncSession, institution_id: str, offset: int, limit: int):
    q = select(Book).where(Book.institution_id == institution_id)
    total = (await db.execute(select(func.count()).select_from(q.subquery()))).scalar()
    result = await db.execute(q.offset(offset).limit(limit))
    return result.scalars().all(), total


async def update_book(db: AsyncSession, book_id: str, data: BookUpdate) -> Book:
    book = (await db.execute(select(Book).where(Book.id == book_id))).scalar_one_or_none()
    if not book:
        raise NotFoundError("Book not found")
    for k, v in data.model_dump(exclude_none=True).items():
        setattr(book, k, v)
    # Sync available copies if total_copies updated
    if data.total_copies is not None:
        issued_count = (
            await db.execute(
                select(func.count()).select_from(BookIssue).where(
                    BookIssue.book_id == book_id,
                    BookIssue.status == IssueStatus.ISSUED,
                )
            )
        ).scalar()
        book.available_copies = max(0, data.total_copies - issued_count)
    await db.flush()
    return book


async def issue_book(db: AsyncSession, data: IssueBookRequest) -> BookIssue:
    book = (await db.execute(select(Book).where(Book.id == data.book_id))).scalar_one_or_none()
    if not book:
        raise NotFoundError("Book not found")
    if book.available_copies < 1:
        raise BusinessRuleError("No copies available for this book")

    # Check student doesn't already have this book
    existing = (
        await db.execute(
            select(BookIssue).where(
                BookIssue.book_id == data.book_id,
                BookIssue.student_id == data.student_id,
                BookIssue.status == IssueStatus.ISSUED,
            )
        )
    ).scalar_one_or_none()
    if existing:
        raise BusinessRuleError("Student already has this book issued")

    issue = BookIssue(
        book_id=str(data.book_id),
        student_id=str(data.student_id),
        issued_on=date.today(),
        due_date=data.due_date,
        status=IssueStatus.ISSUED,
    )
    db.add(issue)
    book.available_copies -= 1
    await db.flush()
    await db.refresh(issue)
    return issue


async def return_book(db: AsyncSession, data: ReturnBookRequest) -> BookIssue:
    issue = (
        await db.execute(select(BookIssue).where(BookIssue.id == data.issue_id))
    ).scalar_one_or_none()
    if not issue:
        raise NotFoundError("Book issue record not found")
    if issue.status == IssueStatus.RETURNED:
        raise BusinessRuleError("Book already returned")

    today = date.today()
    fine = 0.0
    if today > issue.due_date:
        overdue_days = (today - issue.due_date).days
        fine = overdue_days * data.fine_per_day

    issue.returned_on = today
    issue.fine_amount = fine
    issue.status = IssueStatus.RETURNED

    book = (await db.execute(select(Book).where(Book.id == issue.book_id))).scalar_one()
    book.available_copies += 1

    await db.flush()
    return issue


async def list_issues(db: AsyncSession, student_id: str | None, offset: int, limit: int):
    q = select(BookIssue)
    if student_id:
        q = q.where(BookIssue.student_id == student_id)
    total = (await db.execute(select(func.count()).select_from(q.subquery()))).scalar()
    result = await db.execute(q.order_by(BookIssue.issued_on.desc()).offset(offset).limit(limit))
    return result.scalars().all(), total
