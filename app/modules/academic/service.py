from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_
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
    if filter_col is not None and filter_val is not None:
        q = q.where(filter_col == filter_val)
    if hasattr(model, "updated_at"):
        q = q.order_by(model.updated_at.desc(), model.created_at.desc())
    total = (await db.execute(select(func.count()).select_from(q.subquery()))).scalar()
    result = await db.execute(q.offset(offset).limit(limit))
    return result.scalars().all(), total


async def _update(db, model, id_, data):
    obj = await _get_or_404(db, model, id_)
    for k, v in data.model_dump(exclude_none=True).items():
        setattr(obj, k, v)
    await db.flush()
    return obj


async def _delete(db, model, id_):
    obj = await _get_or_404(db, model, id_)
    await db.delete(obj)
    await db.flush()


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


async def delete_academic_year(db, id_):
    await _delete(db, AcademicYear, id_)


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


async def delete_course(db, id_):
    await _delete(db, Course, id_)


# ─── Branch ────────────────────────────────────────────────────────────────

async def create_branch(db, data: BranchCreate):
    ex = (
        await db.execute(
            select(Branch).where(
                Branch.course_id == data.course_id,
                or_(func.lower(Branch.code) == data.code.lower(), func.lower(Branch.name) == data.name.lower()),
            )
        )
    ).scalar_one_or_none()
    if ex:
        raise ConflictError("Branch name or code already exists for this course")
    obj = Branch(**data.model_dump())
    db.add(obj); await db.flush(); await db.refresh(obj)
    return obj

async def list_branches(db, course_id, offset, limit):
    return await _list(db, Branch, Branch.course_id, course_id, offset, limit)

async def update_branch(db, id_, data: BranchUpdate):
    obj = await _get_or_404(db, Branch, id_)
    incoming = data.model_dump(exclude_unset=True)
    course_id = incoming.get("course_id", obj.course_id)
    name = incoming.get("name", obj.name)
    code = incoming.get("code", obj.code)
    ex = (
        await db.execute(
            select(Branch).where(
                Branch.id != obj.id,
                Branch.course_id == course_id,
                or_(func.lower(Branch.code) == str(code).lower(), func.lower(Branch.name) == str(name).lower()),
            )
        )
    ).scalar_one_or_none()
    if ex:
        raise ConflictError("Branch name or code already exists for this course")
    for k, v in incoming.items():
        setattr(obj, k, v)
    await db.flush()
    return obj


async def delete_branch(db, id_):
    await _delete(db, Branch, id_)


# ─── Subject ───────────────────────────────────────────────────────────────

async def create_subject(db, data: SubjectCreate):
    ex = (
        await db.execute(
            select(Subject).where(
                Subject.course_id == data.course_id,
                Subject.class_id == data.class_id,
                Subject.branch_id == data.branch_id,
                or_(func.lower(Subject.code) == data.code.lower(), func.lower(Subject.name) == data.name.lower()),
            )
        )
    ).scalar_one_or_none()
    if ex:
        raise ConflictError("Subject name or code already exists for this class")
    obj = Subject(**data.model_dump())
    db.add(obj); await db.flush(); await db.refresh(obj)
    return obj

async def list_subjects(db, class_id, offset, limit, branch_id=None, course_id=None, academic_year_id=None):
    q = select(Subject)
    if course_id:
        q = q.where(Subject.course_id == course_id)
    if class_id:
        q = q.where(Subject.class_id == class_id)
    if branch_id:
        q = q.join(Class, Class.id == Subject.class_id).where(or_(Subject.branch_id == branch_id, Class.branch_id == branch_id))
    if academic_year_id:
        q = q.where(Subject.academic_year_id == academic_year_id)
    q = q.order_by(Subject.updated_at.desc(), Subject.created_at.desc())
    total = (await db.execute(select(func.count()).select_from(q.subquery()))).scalar()
    result = await db.execute(q.offset(offset).limit(limit))
    return result.scalars().all(), total

async def update_subject(db, id_, data: SubjectUpdate):
    obj = await _get_or_404(db, Subject, id_)
    incoming = data.model_dump(exclude_unset=True)
    course_id = incoming.get("course_id", obj.course_id)
    class_id = incoming.get("class_id", obj.class_id)
    branch_id = incoming.get("branch_id", obj.branch_id)
    name = incoming.get("name", obj.name)
    code = incoming.get("code", obj.code)
    ex = (
        await db.execute(
            select(Subject).where(
                Subject.id != obj.id,
                Subject.course_id == course_id,
                Subject.class_id == class_id,
                Subject.branch_id == branch_id,
                or_(func.lower(Subject.code) == str(code).lower(), func.lower(Subject.name) == str(name).lower()),
            )
        )
    ).scalar_one_or_none()
    if ex:
        raise ConflictError("Subject name or code already exists for this class")
    for k, v in incoming.items():
        setattr(obj, k, v)
    await db.flush()
    return obj


async def delete_subject(db, id_):
    await _delete(db, Subject, id_)


# ─── Class ─────────────────────────────────────────────────────────────────

async def create_class(db, data: ClassCreate):
    ex = (
        await db.execute(
            select(Class).where(
                Class.course_id == data.course_id,
                Class.branch_id == data.branch_id,
                Class.academic_year_id == data.academic_year_id,
                func.lower(Class.name) == data.name.lower(),
                Class.semester == data.semester,
            )
        )
    ).scalar_one_or_none()
    if ex:
        raise ConflictError("Class already exists for this course, branch, year and semester")
    obj = Class(**data.model_dump())
    db.add(obj); await db.flush(); await db.refresh(obj)
    return obj

async def list_classes(db, course_id, offset, limit, branch_id=None, academic_year_id=None):
    q = select(Class)
    if course_id:
        q = q.where(Class.course_id == course_id)
    if branch_id:
        q = q.where(Class.branch_id == branch_id)
    if academic_year_id:
        q = q.where(Class.academic_year_id == academic_year_id)
    q = q.order_by(Class.updated_at.desc(), Class.created_at.desc())
    total = (await db.execute(select(func.count()).select_from(q.subquery()))).scalar()
    result = await db.execute(q.offset(offset).limit(limit))
    return result.scalars().all(), total

async def update_class(db, id_, data: ClassUpdate):
    obj = await _get_or_404(db, Class, id_)
    incoming = data.model_dump(exclude_unset=True)
    course_id = incoming.get("course_id", obj.course_id)
    branch_id = incoming.get("branch_id", obj.branch_id)
    academic_year_id = incoming.get("academic_year_id", obj.academic_year_id)
    name = incoming.get("name", obj.name)
    semester = incoming.get("semester", obj.semester)
    ex = (
        await db.execute(
            select(Class).where(
                Class.id != obj.id,
                Class.course_id == course_id,
                Class.branch_id == branch_id,
                Class.academic_year_id == academic_year_id,
                func.lower(Class.name) == str(name).lower(),
                Class.semester == semester,
            )
        )
    ).scalar_one_or_none()
    if ex:
        raise ConflictError("Class already exists for this course, branch, year and semester")
    for k, v in incoming.items():
        setattr(obj, k, v)
    await db.flush()
    return obj


async def delete_class(db, id_):
    await _delete(db, Class, id_)


# ─── Section ───────────────────────────────────────────────────────────────

async def create_section(db, data: SectionCreate):
    ex = (
        await db.execute(
            select(Section).where(
                Section.class_id == data.class_id,
                func.lower(Section.name) == data.name.lower(),
            )
        )
    ).scalar_one_or_none()
    if ex:
        raise ConflictError("Section already exists for this class")
    obj = Section(**data.model_dump())
    db.add(obj); await db.flush(); await db.refresh(obj)
    return obj

async def list_sections(db, class_id, offset, limit):
    return await _list(db, Section, Section.class_id, class_id, offset, limit)

async def update_section(db, id_, data: SectionUpdate):
    obj = await _get_or_404(db, Section, id_)
    incoming = data.model_dump(exclude_unset=True)
    name = incoming.get("name", obj.name)
    ex = (
        await db.execute(
            select(Section).where(
                Section.id != obj.id,
                Section.class_id == obj.class_id,
                func.lower(Section.name) == str(name).lower(),
            )
        )
    ).scalar_one_or_none()
    if ex:
        raise ConflictError("Section already exists for this class")
    for k, v in incoming.items():
        setattr(obj, k, v)
    await db.flush()
    return obj


async def delete_section(db, id_):
    await _delete(db, Section, id_)
