from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_
from app.modules.organizations.model import Organization
from app.modules.institutions.model import Institution
from app.modules.organizations.schema import OrgCreate, OrgUpdate, InstitutionCreate, InstitutionUpdate
from app.core.exceptions import NotFoundError, ConflictError


async def create_org(db: AsyncSession, data: OrgCreate) -> Organization:
    ex = await db.execute(select(Organization).where(Organization.slug == data.slug))
    if ex.scalar_one_or_none():
        raise ConflictError("Slug already in use")
    org = Organization(**data.model_dump())
    db.add(org)
    await db.flush()
    await db.refresh(org)
    return org


async def list_orgs(db: AsyncSession, offset: int, limit: int, search: str | None = None):
    q = select(Organization)
    if search:
        term = f"%{search.strip()}%"
        q = q.where(or_(Organization.name.ilike(term), Organization.slug.ilike(term)))

    total = (await db.execute(select(func.count()).select_from(q.subquery()))).scalar()
    result = await db.execute(q.offset(offset).limit(limit))
    return result.scalars().all(), total


async def update_org(db: AsyncSession, org_id: str, data: OrgUpdate) -> Organization:
    org = (await db.execute(select(Organization).where(Organization.id == org_id))).scalar_one_or_none()
    if not org:
        raise NotFoundError("Organization not found")

    incoming = data.model_dump(exclude_none=True)
    if "slug" in incoming and incoming["slug"] != org.slug:
        ex = await db.execute(select(Organization).where(Organization.slug == incoming["slug"]))
        exists = ex.scalar_one_or_none()
        if exists and exists.id != org.id:
            raise ConflictError("Slug already in use")

    for k, v in incoming.items():
        setattr(org, k, v)
    await db.flush()
    return org


async def create_institution(db: AsyncSession, data: InstitutionCreate) -> Institution:
    ex = await db.execute(select(Institution).where(Institution.code == data.code))
    if ex.scalar_one_or_none():
        raise ConflictError("Institution code already in use")
    inst = Institution(**data.model_dump())
    db.add(inst)
    await db.flush()
    await db.refresh(inst)
    return inst


async def list_institutions(db: AsyncSession, org_id: str, offset: int, limit: int, search: str | None = None):
    # If search is present, search globally across institutions (ignore org_id filter).
    q = select(Institution)
    if not search:
        q = q.where(Institution.org_id == org_id)

    if search:
        terms = [t for t in search.strip().split() if t]
        for t in terms:
            like = f"%{t}%"
            q = q.where(or_(Institution.name.ilike(like), Institution.code.ilike(like), Institution.address.ilike(like)))

    total = (await db.execute(select(func.count()).select_from(q.subquery()))).scalar()
    result = await db.execute(q.offset(offset).limit(limit))
    return result.scalars().all(), total


async def update_institution(db: AsyncSession, inst_id: str, data: InstitutionUpdate) -> Institution:
    inst = (await db.execute(select(Institution).where(Institution.id == inst_id))).scalar_one_or_none()
    if not inst:
        raise NotFoundError("Institution not found")

    incoming = data.model_dump(exclude_none=True)
    if "code" in incoming and incoming["code"] != inst.code:
        ex = await db.execute(select(Institution).where(Institution.code == incoming["code"]))
        exists = ex.scalar_one_or_none()
        if exists and exists.id != inst.id:
            raise ConflictError("Institution code already in use")

    for k, v in incoming.items():
        setattr(inst, k, v)
    await db.flush()
    return inst
