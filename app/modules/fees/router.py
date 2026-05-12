from typing import Annotated
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.modules.fees import service
from app.modules.fees.schema import (
    FeeTypeCreate, FeeTypeOut,
    FeeStructureCreate, FeeStructureOut,
    StudentFeeCreate, StudentFeeOut, StudentFeeListOut,
    PaymentCreate, PaymentOut,
)
from app.core.dependencies import CurrentUser, require_permission
from app.constants.permissions import FEE_MANAGE, FEE_COLLECT
from app.utils.response import ok, paginated
from app.utils.pagination import PaginationParams
from app.modules.logs.service import log_activity

router = APIRouter(prefix="/fees", tags=["Fees"])
DB = Annotated[AsyncSession, Depends(get_db)]


# ─── Fee Types ─────────────────────────────────────────────────────────────

@router.post("/types", response_model=dict, dependencies=[Depends(require_permission(FEE_MANAGE))])
async def create_fee_type(payload: FeeTypeCreate, current_user: CurrentUser, db: DB):
    payload = payload.model_copy(update={"institution_id": current_user["institution_id"]})
    obj = await service.create_fee_type(db, payload)
    await log_activity(
        db,
        module="fees",
        action="fee_type_create",
        actor_user_id=current_user["id"],
        institution_id=current_user["institution_id"],
        entity_type="fee_type",
        entity_id=str(obj.id),
        message="Fee type created",
        meta={"name": obj.name},
    )
    return ok(data=FeeTypeOut.model_validate(obj).model_dump(), message="Fee type created")


@router.get("/types", response_model=dict, dependencies=[Depends(require_permission(FEE_MANAGE))])
async def list_fee_types(
    current_user: CurrentUser,
    db: DB,
    pagination: Annotated[PaginationParams, Depends()],
    institution_id: str | None = None,
):
    items, total = await service.list_fee_types(db, current_user["institution_id"], pagination.offset, pagination.page_size)
    return paginated(
        [FeeTypeOut.model_validate(i).model_dump() for i in items],
        total, pagination.page, pagination.page_size,
    )


# ─── Fee Structures ────────────────────────────────────────────────────────

@router.post("/structures", response_model=dict, dependencies=[Depends(require_permission(FEE_MANAGE))])
async def create_fee_structure(payload: FeeStructureCreate, current_user: CurrentUser, db: DB):
    obj = await service.create_fee_structure(db, payload, current_user["institution_id"])
    await log_activity(
        db,
        module="fees",
        action="fee_structure_create",
        actor_user_id=current_user["id"],
        institution_id=current_user["institution_id"],
        entity_type="fee_structure",
        entity_id=str(obj.id),
        message="Fee structure created",
        meta=payload.model_dump(),
    )
    return ok(data=FeeStructureOut.model_validate(obj).model_dump(), message="Fee structure created")


@router.get("/structures", response_model=dict, dependencies=[Depends(require_permission(FEE_MANAGE))])
async def list_fee_structures(
    fee_type_id: str, db: DB, pagination: Annotated[PaginationParams, Depends()]
):
    items, total = await service.list_fee_structures(db, fee_type_id, pagination.offset, pagination.page_size)
    return paginated(
        [FeeStructureOut.model_validate(i).model_dump() for i in items],
        total, pagination.page, pagination.page_size,
    )


# ─── Student Fees ──────────────────────────────────────────────────────────

@router.post("/student-fees", response_model=dict, dependencies=[Depends(require_permission(FEE_MANAGE))])
async def create_student_fee(payload: StudentFeeCreate, current_user: CurrentUser, db: DB):
    obj = await service.create_student_fee(db, payload, current_user["institution_id"])
    await log_activity(
        db,
        module="fees",
        action="student_fee_assign",
        actor_user_id=current_user["id"],
        institution_id=current_user["institution_id"],
        entity_type="student_fee",
        entity_id=str(obj.id),
        message="Student fee assigned",
        meta=payload.model_dump(),
    )
    return ok(data=StudentFeeOut.model_validate(obj).model_dump(), message="Student fee created")


@router.get("/student-fees", response_model=dict, dependencies=[Depends(require_permission(FEE_MANAGE))])
async def list_all_student_fees(
    current_user: CurrentUser,
    db: DB,
    pagination: Annotated[PaginationParams, Depends()],
    student_id: str | None = None,
):
    rows, total = await service.list_all_student_fees(
        db, pagination.offset, pagination.page_size, student_id, current_user["institution_id"]
    )
    items = []
    for student_fee, student_name, roll_number, fee_type_name, course_name, academic_year_label, frequency in rows:
        data = StudentFeeListOut.model_validate(student_fee).model_dump()
        data.update(
            {
                "student_name": student_name,
                "roll_number": roll_number,
                "fee_type_name": fee_type_name,
                "course_name": course_name,
                "academic_year_label": academic_year_label,
                "frequency": frequency,
            }
        )
        items.append(data)
    return paginated(items, total, pagination.page, pagination.page_size)


@router.get("/student-fees/{student_id}", response_model=dict, dependencies=[Depends(require_permission(FEE_MANAGE))])
async def list_student_fees(student_id: str, current_user: CurrentUser, db: DB):
    items = await service.list_student_fees(db, student_id, current_user["institution_id"])
    return ok(data=[StudentFeeOut.model_validate(i).model_dump() for i in items])


# ─── Payments ──────────────────────────────────────────────────────────────

@router.post("/payments", response_model=dict, dependencies=[Depends(require_permission(FEE_COLLECT))])
async def collect_payment(payload: PaymentCreate, current_user: CurrentUser, db: DB):
    payment = await service.collect_payment(db, payload, current_user["institution_id"], current_user["id"])
    return ok(data=PaymentOut.model_validate(payment).model_dump(), message="Payment recorded")


@router.get("/payments/{student_fee_id}", response_model=dict, dependencies=[Depends(require_permission(FEE_COLLECT))])
async def list_payments(student_fee_id: str, current_user: CurrentUser, db: DB):
    items = await service.list_payments(db, student_fee_id, current_user["institution_id"])
    return ok(data=[PaymentOut.model_validate(i).model_dump() for i in items])
