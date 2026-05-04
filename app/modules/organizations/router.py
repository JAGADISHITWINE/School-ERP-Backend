from typing import Annotated
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.modules.organizations import service
from app.modules.organizations.schema import OrgCreate, OrgUpdate, OrgOut, InstitutionCreate, InstitutionUpdate, InstitutionOut
from app.core.dependencies import require_permission
from app.constants.permissions import ORG_MANAGE, INSTITUTION_MANAGE
from app.utils.response import ok, paginated
from app.utils.pagination import PaginationParams

router = APIRouter(tags=["Organizations & Institutions"])


@router.post("/organizations", response_model=dict, dependencies=[Depends(require_permission(ORG_MANAGE))])
async def create_org(payload: OrgCreate, db: Annotated[AsyncSession, Depends(get_db)]):
    org = await service.create_org(db, payload)
    return ok(data=OrgOut.model_validate(org).model_dump(), message="Organization created")


@router.get("/organizations", response_model=dict, dependencies=[Depends(require_permission(ORG_MANAGE))])
async def list_orgs(db: Annotated[AsyncSession, Depends(get_db)], pagination: Annotated[PaginationParams, Depends()], search: str | None = Query(default=None)):
    orgs, total = await service.list_orgs(db, pagination.offset, pagination.page_size, search)
    return paginated([OrgOut.model_validate(o).model_dump() for o in orgs], total, pagination.page, pagination.page_size)


@router.patch("/organizations/{org_id}", response_model=dict, dependencies=[Depends(require_permission(ORG_MANAGE))])
async def update_org(org_id: str, payload: OrgUpdate, db: Annotated[AsyncSession, Depends(get_db)]):
    org = await service.update_org(db, org_id, payload)
    return ok(data=OrgOut.model_validate(org).model_dump(), message="Updated")


@router.post("/institutions", response_model=dict, dependencies=[Depends(require_permission(INSTITUTION_MANAGE))])
async def create_institution(payload: InstitutionCreate, db: Annotated[AsyncSession, Depends(get_db)]):
    inst = await service.create_institution(db, payload)
    return ok(data=InstitutionOut.model_validate(inst).model_dump(), message="Institution created")


@router.get("/institutions", response_model=dict, dependencies=[Depends(require_permission(INSTITUTION_MANAGE))])
async def list_institutions(org_id: str, db: Annotated[AsyncSession, Depends(get_db)], pagination: Annotated[PaginationParams, Depends()], search: str | None = Query(default=None)):
    insts, total = await service.list_institutions(db, org_id, pagination.offset, pagination.page_size, search)
    return paginated([InstitutionOut.model_validate(i).model_dump() for i in insts], total, pagination.page, pagination.page_size)


@router.patch("/institutions/{inst_id}", response_model=dict, dependencies=[Depends(require_permission(INSTITUTION_MANAGE))])
async def update_institution(inst_id: str, payload: InstitutionUpdate, db: Annotated[AsyncSession, Depends(get_db)]):
    inst = await service.update_institution(db, inst_id, payload)
    return ok(data=InstitutionOut.model_validate(inst).model_dump(), message="Updated")
