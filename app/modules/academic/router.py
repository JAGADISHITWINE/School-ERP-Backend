from typing import Annotated
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.modules.academic import service
from app.modules.academic.schema import (
    AcademicYearCreate, AcademicYearUpdate, AcademicYearOut,
    CourseCreate, CourseUpdate, CourseOut,
    BranchCreate, BranchUpdate, BranchOut,
    SubjectCreate, SubjectUpdate, SubjectOut,
    ClassCreate, ClassUpdate, ClassOut,
    SectionCreate, SectionUpdate, SectionOut,
)
from app.core.dependencies import CurrentUser, require_permission
from app.constants.permissions import (
    ACADEMIC_YEAR_MANAGE, COURSE_MANAGE, BRANCH_MANAGE,
    SUBJECT_MANAGE, CLASS_MANAGE, SECTION_MANAGE
)
from app.utils.response import ok, paginated
from app.utils.pagination import PaginationParams

router = APIRouter(tags=["Academic Masters"])

perm = lambda p: Depends(require_permission(p))
DB = Annotated[AsyncSession, Depends(get_db)]
Pagination = Annotated[PaginationParams, Depends()]


# ─── Academic Years ────────────────────────────────────────────────────────

@router.post("/academic-years", response_model=dict, dependencies=[perm(ACADEMIC_YEAR_MANAGE)])
async def create_academic_year(payload: AcademicYearCreate, db: DB):
    obj = await service.create_academic_year(db, payload)
    return ok(data=AcademicYearOut.model_validate(obj).model_dump(), message="Academic year created")

@router.get("/academic-years", response_model=dict, dependencies=[perm(ACADEMIC_YEAR_MANAGE)])
async def list_academic_years(institution_id: str, db: DB, pagination: Pagination):
    items, total = await service.list_academic_years(db, institution_id, pagination.offset, pagination.page_size)
    return paginated([AcademicYearOut.model_validate(i).model_dump() for i in items], total, pagination.page, pagination.page_size)

@router.patch("/academic-years/{id}", response_model=dict, dependencies=[perm(ACADEMIC_YEAR_MANAGE)])
async def update_academic_year(id: str, payload: AcademicYearUpdate, db: DB):
    obj = await service.update_academic_year(db, id, payload)
    return ok(data=AcademicYearOut.model_validate(obj).model_dump())


# ─── Courses ───────────────────────────────────────────────────────────────

@router.post("/courses", response_model=dict, dependencies=[perm(COURSE_MANAGE)])
async def create_course(payload: CourseCreate, db: DB):
    obj = await service.create_course(db, payload)
    return ok(data=CourseOut.model_validate(obj).model_dump(), message="Course created")

@router.get("/courses", response_model=dict, dependencies=[perm(COURSE_MANAGE)])
async def list_courses(institution_id: str, db: DB, pagination: Pagination):
    items, total = await service.list_courses(db, institution_id, pagination.offset, pagination.page_size)
    return paginated([CourseOut.model_validate(i).model_dump() for i in items], total, pagination.page, pagination.page_size)

@router.patch("/courses/{id}", response_model=dict, dependencies=[perm(COURSE_MANAGE)])
async def update_course(id: str, payload: CourseUpdate, db: DB):
    obj = await service.update_course(db, id, payload)
    return ok(data=CourseOut.model_validate(obj).model_dump())


# ─── Branches ──────────────────────────────────────────────────────────────

@router.post("/branches", response_model=dict, dependencies=[perm(BRANCH_MANAGE)])
async def create_branch(payload: BranchCreate, db: DB):
    obj = await service.create_branch(db, payload)
    return ok(data=BranchOut.model_validate(obj).model_dump(), message="Branch created")

@router.get("/branches", response_model=dict, dependencies=[perm(BRANCH_MANAGE)])
async def list_branches(course_id: str, db: DB, pagination: Pagination):
    items, total = await service.list_branches(db, course_id, pagination.offset, pagination.page_size)
    return paginated([BranchOut.model_validate(i).model_dump() for i in items], total, pagination.page, pagination.page_size)

@router.patch("/branches/{id}", response_model=dict, dependencies=[perm(BRANCH_MANAGE)])
async def update_branch(id: str, payload: BranchUpdate, db: DB):
    obj = await service.update_branch(db, id, payload)
    return ok(data=BranchOut.model_validate(obj).model_dump())


# ─── Subjects ──────────────────────────────────────────────────────────────

@router.post("/subjects", response_model=dict, dependencies=[perm(SUBJECT_MANAGE)])
async def create_subject(payload: SubjectCreate, db: DB):
    obj = await service.create_subject(db, payload)
    return ok(data=SubjectOut.model_validate(obj).model_dump(), message="Subject created")

@router.get("/subjects", response_model=dict, dependencies=[perm(SUBJECT_MANAGE)])
async def list_subjects(
    db: Annotated[AsyncSession, Depends(get_db)],
    pagination: Annotated[PaginationParams, Depends()],
    class_id: str | None = None,
    branch_id: str | None = None,
):
    items, total = await service.list_subjects(db, class_id, pagination.offset, pagination.page_size, branch_id=branch_id)
    return paginated([SubjectOut.model_validate(i).model_dump() for i in items], total, pagination.page, pagination.page_size)

@router.patch("/subjects/{id}", response_model=dict, dependencies=[perm(SUBJECT_MANAGE)])
async def update_subject(id: str, payload: SubjectUpdate, db: DB):
    obj = await service.update_subject(db, id, payload)
    return ok(data=SubjectOut.model_validate(obj).model_dump())


# ─── Classes ───────────────────────────────────────────────────────────────

@router.post("/classes", response_model=dict, dependencies=[perm(CLASS_MANAGE)])
async def create_class(payload: ClassCreate, db: DB):
    obj = await service.create_class(db, payload)
    return ok(data=ClassOut.model_validate(obj).model_dump(), message="Class created")

@router.get("/classes", response_model=dict, dependencies=[perm(CLASS_MANAGE)])
async def list_classes(
    db: Annotated[AsyncSession, Depends(get_db)],
    pagination: Annotated[PaginationParams, Depends()],
    course_id: str | None = None,
    branch_id: str | None = None,
):
    items, total = await service.list_classes(db, course_id, pagination.offset, pagination.page_size, branch_id=branch_id)
    return paginated([ClassOut.model_validate(i).model_dump() for i in items], total, pagination.page, pagination.page_size)

@router.patch("/classes/{id}", response_model=dict, dependencies=[perm(CLASS_MANAGE)])
async def update_class(id: str, payload: ClassUpdate, db: DB):
    obj = await service.update_class(db, id, payload)
    return ok(data=ClassOut.model_validate(obj).model_dump())


# ─── Sections ──────────────────────────────────────────────────────────────

@router.post("/sections", response_model=dict, dependencies=[perm(SECTION_MANAGE)])
async def create_section(payload: SectionCreate, db: DB):
    obj = await service.create_section(db, payload)
    return ok(data=SectionOut.model_validate(obj).model_dump(), message="Section created")

@router.get("/sections", response_model=dict, dependencies=[perm(SECTION_MANAGE)])
async def list_sections(class_id: str, db: DB, pagination: Pagination):
    items, total = await service.list_sections(db, class_id, pagination.offset, pagination.page_size)
    return paginated([SectionOut.model_validate(i).model_dump() for i in items], total, pagination.page, pagination.page_size)

@router.patch("/sections/{id}", response_model=dict, dependencies=[perm(SECTION_MANAGE)])
async def update_section(id: str, payload: SectionUpdate, db: DB):
    obj = await service.update_section(db, id, payload)
    return ok(data=SectionOut.model_validate(obj).model_dump())
