from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.modules.academic.model import AcademicYear, Course, Branch, Subject, Class, Section
from app.modules.academic.schema import (
    AcademicYearCreate, AcademicYearUpdate,
    CourseCreate, CourseUpdate,
    BranchCreate, BranchUpdate,
    SubjectCreate, SubjectUpdate,
    ClassCreate, ClassUpdate,
    SectionCreate, SectionUpdate,
)
from app.core.exceptions import NotFoundError, ConflictError


# ─── Generic helpers ─────────────────────────────────────────────────────────

async def _get_or_404(db, model, id_):
    obj = (await db.execute(select(model).where(model.id == id_))).scalar_one_or_none()
    if not obj:
        raise NotFoundError(f"{model.__name__} not found")
    return obj


async def _list(db, model, filter_col, filter_val, offset, limit):
    q = select(model)
    if filter_col is not None:
        q = q.where(filter_col == filter_val)
    total = (await db.execute(select(func.count()).select_from(q.subquery()))).scalar()
    result = await db.execute(q.offset(offset).limit(limit))
    return result.scalars().all(), total


async def _update(db, model, id_, data):
    obj = await _get_or_404(db, model, id_)
    for k, v in data.model_dump(exclude_none=True).items():
        setattr(obj, k, v)
    await db.flush()
    return obj


# ─── Academic Year ─────────────────────────────────────────────────────────

async def create_academic_year(db, data: AcademicYearCreate):
    if data.is_current:
        # unset current flag on others for same institution
        others = (await db.execute(
            select(AcademicYear).where(AcademicYear.institution_id == data.institution_id, AcademicYear.is_current == True)
        )).scalars().all()
        for o in others:
            o.is_current = False
    obj = AcademicYear(**data.model_dump())
    db.add(obj); await db.flush(); await db.refresh(obj)
    return obj

async def list_academic_years(db, institution_id, offset, limit):
    return await _list(db, AcademicYear, AcademicYear.institution_id, institution_id, offset, limit)

async def update_academic_year(db, id_, data: AcademicYearUpdate):
    obj = await _get_or_404(db, AcademicYear, id_)
    incoming = data.model_dump(exclude_none=True)
    if incoming.get("is_current") is True:
        others = (await db.execute(
            select(AcademicYear).where(
                AcademicYear.institution_id == obj.institution_id,
                AcademicYear.id != obj.id,
                AcademicYear.is_current == True,
            )
        )).scalars().all()
        for other in others:
            other.is_current = False

    for k, v in incoming.items():
        setattr(obj, k, v)
    await db.flush()
    return obj


# ─── Course ────────────────────────────────────────────────────────────────

async def create_course(db, data: CourseCreate):
    ex = (await db.execute(select(Course).where(Course.code == data.code))).scalar_one_or_none()
    if ex:
        raise ConflictError("Course code already exists")
    obj = Course(**data.model_dump())
    db.add(obj); await db.flush(); await db.refresh(obj)
    return obj

async def list_courses(db, institution_id, offset, limit):
    return await _list(db, Course, Course.institution_id, institution_id, offset, limit)

async def update_course(db, id_, data: CourseUpdate):
    return await _update(db, Course, id_, data)


# ─── Branch ────────────────────────────────────────────────────────────────

async def create_branch(db, data: BranchCreate):
    obj = Branch(**data.model_dump())
    db.add(obj); await db.flush(); await db.refresh(obj)
    return obj

async def list_branches(db, course_id, offset, limit):
    return await _list(db, Branch, Branch.course_id, course_id, offset, limit)

async def update_branch(db, id_, data: BranchUpdate):
    return await _update(db, Branch, id_, data)


# ─── Subject ───────────────────────────────────────────────────────────────

async def create_subject(db, data: SubjectCreate):
    obj = Subject(**data.model_dump())
    db.add(obj); await db.flush(); await db.refresh(obj)
    return obj

async def list_subjects(db, branch_id, offset, limit):
    return await _list(db, Subject, Subject.branch_id, branch_id, offset, limit)

async def update_subject(db, id_, data: SubjectUpdate):
    obj = await _get_or_404(db, Subject, id_)
    incoming = data.model_dump(exclude_unset=True)
    for k, v in incoming.items():
        setattr(obj, k, v)
    await db.flush()
    return obj


# ─── Class ─────────────────────────────────────────────────────────────────

async def create_class(db, data: ClassCreate):
    obj = Class(**data.model_dump())
    db.add(obj); await db.flush(); await db.refresh(obj)
    return obj

async def list_classes(db, branch_id, offset, limit):
    return await _list(db, Class, Class.branch_id, branch_id, offset, limit)

async def update_class(db, id_, data: ClassUpdate):
    obj = await _get_or_404(db, Class, id_)
    incoming = data.model_dump(exclude_unset=True)
    for k, v in incoming.items():
        setattr(obj, k, v)
    await db.flush()
    return obj


# ─── Section ───────────────────────────────────────────────────────────────

async def create_section(db, data: SectionCreate):
    obj = Section(**data.model_dump())
    db.add(obj); await db.flush(); await db.refresh(obj)
    return obj

async def list_sections(db, class_id, offset, limit):
    return await _list(db, Section, Section.class_id, class_id, offset, limit)

async def update_section(db, id_, data: SectionUpdate):
    return await _update(db, Section, id_, data)
