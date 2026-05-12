from typing import Annotated
from datetime import date
from fastapi import APIRouter, Depends, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.session import get_db
from app.modules.teachers import service
from app.modules.teachers.model import TimetableDay, Teacher
from app.modules.teachers.schema import (
    TeacherCreate,
    TeacherOut,
    SubjectAssignRequest,
    TeacherClassAssignRequest,
    TeacherClassOut,
    ClassMentorCreate,
    ClassMentorUpdate,
    ClassMentorOut,
    TeacherCandidateOut,
    TeacherTimetableCreate,
    TeacherTimetableUpdate,
    TeacherTimetableReassignRequest,
    TeacherTimetableOut,
    HODLinkCreate,
    HODLinkUpdate,
    HODLinkOut,
    TeacherHODSubjectLinkCreate,
    TeacherHODSubjectLinkUpdate,
    TeacherHODSubjectLinkOut,
)
from app.modules.users.model import User
from app.core.dependencies import CurrentUser, require_permission
from app.core.exceptions import NotFoundError
from app.constants.permissions import TEACHER_CREATE, TEACHER_READ, TEACHER_UPDATE
from app.utils.response import ok, paginated
from app.utils.pagination import PaginationParams

router = APIRouter(prefix="/teachers", tags=["Teachers"])
DB = Annotated[AsyncSession, Depends(get_db)]


@router.post("", response_model=dict, dependencies=[Depends(require_permission(TEACHER_CREATE))])
async def create_teacher(payload: TeacherCreate, current_user: CurrentUser, db: DB):
    teacher = await service.create_teacher(
        db,
        payload,
        actor_institution_id=current_user["institution_id"],
    )
    return ok(data={"id": str(teacher.id)}, message="Teacher created")


@router.get("/candidates", response_model=dict, dependencies=[Depends(require_permission(TEACHER_READ))])
async def list_teacher_candidates(current_user: CurrentUser, db: DB):
    users = await service.list_teacher_candidates(db, current_user["institution_id"])
    items = [
        TeacherCandidateOut(
            user_id=user.id,
            institution_id=user.institution_id,
            full_name=user.full_name,
            email=user.email,
            username=user.username,
            phone=user.phone,
        ).model_dump()
        for user in users
    ]
    return ok(data=items)


@router.get("/hod-candidates", response_model=dict, dependencies=[Depends(require_permission(TEACHER_READ))])
async def list_hod_candidates(current_user: CurrentUser, db: DB):
    rows = await service.list_hod_teacher_candidates(db, current_user["institution_id"])
    return ok(data=rows)


@router.get("", response_model=dict, dependencies=[Depends(require_permission(TEACHER_READ))])
async def list_teachers(current_user: CurrentUser, db: DB, pagination: Annotated[PaginationParams, Depends()]):
    teachers, total = await service.list_teachers(
        db,
        current_user["institution_id"],
        pagination.offset,
        pagination.page_size,
        current_user,
    )
    out = []
    for t in teachers:
        user = (await db.execute(select(User).where(User.id == t.user_id))).scalar_one()
        out.append(
            TeacherOut(
                id=t.id,
                user_id=t.user_id,
                employee_code=t.employee_code,
                designation=t.designation,
                joined_at=t.joined_at,
                full_name=user.full_name,
                email=user.email,
                username=user.username,
                phone=user.phone,
                assigned_classes=[
                    TeacherClassOut(**item)
                    for item in await service.list_teacher_classes(db, str(t.id))
                ],
            ).model_dump()
        )
    return paginated(out, total, pagination.page, pagination.page_size)


@router.get("/self/teaching-scope", response_model=dict)
async def my_teaching_scope(
    current_user: CurrentUser,
    db: DB,
    branch_id: str | None = None,
    class_id: str | None = None,
    section_id: str | None = None,
):
    teacher = (await db.execute(select(Teacher).where(Teacher.user_id == current_user["id"]))).scalar_one_or_none()
    if not teacher:
        raise NotFoundError("Teacher profile not found for current user")
    data = await service.list_teacher_teaching_scope(
        db,
        str(teacher.id),
        branch_id=branch_id,
        class_id=class_id,
        section_id=section_id,
    )
    return ok(data=data)


@router.get("/class-mentors", response_model=dict, dependencies=[Depends(require_permission(TEACHER_READ))])
async def list_class_mentors(
    current_user: CurrentUser,
    db: DB,
    academic_year_id: str | None = None,
    branch_id: str | None = None,
    class_id: str | None = None,
    section_id: str | None = None,
):
    rows = await service.list_class_mentors(
        db,
        current_user,
        academic_year_id=academic_year_id,
        branch_id=branch_id,
        class_id=class_id,
        section_id=section_id,
    )
    return ok(data=[ClassMentorOut(**row).model_dump() for row in rows])


@router.post("/class-mentors", response_model=dict, dependencies=[Depends(require_permission(TEACHER_UPDATE))])
async def create_class_mentor(payload: ClassMentorCreate, current_user: CurrentUser, db: DB):
    mentor = await service.create_class_mentor(db, payload, current_user)
    return ok(data={"id": str(mentor.id)}, message="Class mentor assigned")


@router.patch("/class-mentors/{mentor_id}", response_model=dict, dependencies=[Depends(require_permission(TEACHER_UPDATE))])
async def update_class_mentor(mentor_id: str, payload: ClassMentorUpdate, current_user: CurrentUser, db: DB):
    mentor = await service.update_class_mentor(db, mentor_id, payload, current_user)
    return ok(data={"id": str(mentor.id)}, message="Class mentor updated")


@router.delete("/class-mentors/{mentor_id}", response_model=dict, dependencies=[Depends(require_permission(TEACHER_UPDATE))])
async def delete_class_mentor(mentor_id: str, current_user: CurrentUser, db: DB):
    await service.delete_class_mentor(db, mentor_id, current_user)
    return ok(message="Class mentor removed")


@router.get("/{teacher_id}/teaching-scope", response_model=dict, dependencies=[Depends(require_permission(TEACHER_READ))])
async def list_teacher_teaching_scope(
    teacher_id: str,
    current_user: CurrentUser,
    db: DB,
    branch_id: str | None = None,
    class_id: str | None = None,
    section_id: str | None = None,
):
    await service.assert_can_view_teacher(db, current_user, teacher_id)
    data = await service.list_teacher_teaching_scope(
        db,
        teacher_id,
        branch_id=branch_id,
        class_id=class_id,
        section_id=section_id,
    )
    return ok(data=data)


@router.get("/{teacher_id}", response_model=dict, dependencies=[Depends(require_permission(TEACHER_READ))])
async def get_teacher(teacher_id: str, current_user: CurrentUser, db: DB):
    await service.assert_can_view_teacher(db, current_user, teacher_id)
    teacher = await service.get_teacher(db, teacher_id)
    user = (await db.execute(select(User).where(User.id == teacher.user_id))).scalar_one()
    data = TeacherOut(
        id=teacher.id,
        user_id=teacher.user_id,
        employee_code=teacher.employee_code,
        designation=teacher.designation,
        joined_at=teacher.joined_at,
        full_name=user.full_name,
        email=user.email,
        username=user.username,
        phone=user.phone,
        assigned_classes=[
            TeacherClassOut(**item)
            for item in await service.list_teacher_classes(db, teacher_id)
        ],
    ).model_dump()
    return ok(data=data)


@router.post("/{teacher_id}/subjects", response_model=dict, dependencies=[Depends(require_permission(TEACHER_UPDATE))])
async def assign_subject(teacher_id: str, payload: SubjectAssignRequest, db: DB):
    ts = await service.assign_subject(db, teacher_id, payload)
    return ok(data={"id": str(ts.id)}, message="Subject assigned")


@router.get("/{teacher_id}/classes", response_model=dict, dependencies=[Depends(require_permission(TEACHER_READ))])
async def list_teacher_classes(teacher_id: str, current_user: CurrentUser, db: DB):
    await service.assert_can_view_teacher(db, current_user, teacher_id)
    items = await service.list_teacher_classes(db, teacher_id)
    return ok(data=[TeacherClassOut(**item).model_dump() for item in items])


@router.post("/{teacher_id}/classes", response_model=dict, dependencies=[Depends(require_permission(TEACHER_UPDATE))])
async def assign_class(teacher_id: str, payload: TeacherClassAssignRequest, db: DB):
    link = await service.assign_class(db, teacher_id, payload)
    return ok(data={"id": str(link.id)}, message="Class linked to teacher")


@router.delete("/{teacher_id}/classes/{class_id}", response_model=dict, dependencies=[Depends(require_permission(TEACHER_UPDATE))])
async def remove_class(teacher_id: str, class_id: str, db: DB):
    await service.remove_class(db, teacher_id, class_id)
    return ok(message="Class unlinked from teacher")


@router.post("/links/hod", response_model=dict, dependencies=[Depends(require_permission(TEACHER_UPDATE))])
async def create_hod_link(payload: HODLinkCreate, db: DB):
    link = await service.create_hod_link(
        db,
        payload.hod_teacher_id,
        payload.institution_id,
        payload.course_id,
        payload.branch_id,
        payload.hod_user_id,
    )
    return ok(data={"id": str(link.id)}, message="HOD linked")


@router.get("/links/hod", response_model=dict, dependencies=[Depends(require_permission(TEACHER_READ))])
async def list_hod_links(
    current_user: CurrentUser,
    db: DB,
    institution_id: str | None = None,
    course_id: str | None = None,
    branch_id: str | None = None,
):
    rows = await service.list_hod_links(
        db,
        institution_id=institution_id,
        course_id=course_id,
        branch_id=branch_id,
        current_user=current_user,
    )
    return ok(data=[HODLinkOut(**row).model_dump() for row in rows])


@router.delete("/links/hod/{link_id}", response_model=dict, dependencies=[Depends(require_permission(TEACHER_UPDATE))])
async def remove_hod_link(link_id: str, db: DB):
    await service.remove_hod_link(db, link_id)
    return ok(message="HOD link removed")


@router.patch("/links/hod/{link_id}", response_model=dict, dependencies=[Depends(require_permission(TEACHER_UPDATE))])
async def update_hod_link(link_id: str, payload: HODLinkUpdate, db: DB):
    link = await service.update_hod_link(
        db,
        link_id,
        payload.hod_teacher_id,
        payload.institution_id,
        payload.course_id,
        payload.branch_id,
        payload.hod_user_id,
    )
    return ok(data={"id": str(link.id)}, message="HOD link updated")


@router.post("/links/teacher-hod-subjects", response_model=dict, dependencies=[Depends(require_permission(TEACHER_UPDATE))])
async def create_teacher_hod_subject_links(payload: TeacherHODSubjectLinkCreate, db: DB):
    result = await service.create_teacher_hod_subject_links(
        db,
        payload.teacher_id,
        payload.hod_link_id,
        payload.section_id,
        payload.subject_ids,
    )
    links = result["created"]
    skipped_subject_ids = result["skipped_subject_ids"]
    return ok(
        data={
            "created_ids": [str(link.id) for link in links],
            "created_count": len(links),
            "skipped_count": len(skipped_subject_ids),
            "skipped_subject_ids": skipped_subject_ids,
        },
        message="Teacher linked with HOD subjects" if links else "Selected teacher links already exist",
    )


@router.get("/links/teacher-hod-subjects", response_model=dict, dependencies=[Depends(require_permission(TEACHER_READ))])
async def list_teacher_hod_subject_links(
    current_user: CurrentUser,
    db: DB,
    institution_id: str | None = None,
    course_id: str | None = None,
    branch_id: str | None = None,
):
    rows = await service.list_teacher_hod_subject_links(
        db,
        institution_id=institution_id,
        course_id=course_id,
        branch_id=branch_id,
        current_user=current_user,
    )
    return ok(data=[TeacherHODSubjectLinkOut(**row).model_dump() for row in rows])


@router.delete(
    "/links/teacher-hod-subjects/{link_id}",
    response_model=dict,
    dependencies=[Depends(require_permission(TEACHER_UPDATE))],
)
async def remove_teacher_hod_subject_link(link_id: str, db: DB):
    await service.remove_teacher_hod_subject_link(db, link_id)
    return ok(message="Teacher-HOD subject link removed")


@router.patch(
    "/links/teacher-hod-subjects/{link_id}",
    response_model=dict,
    dependencies=[Depends(require_permission(TEACHER_UPDATE))],
)
async def update_teacher_hod_subject_link(link_id: str, payload: TeacherHODSubjectLinkUpdate, db: DB):
    link = await service.update_teacher_hod_subject_link(
        db,
        link_id,
        payload.teacher_id,
        payload.hod_link_id,
        payload.section_id,
        payload.subject_id,
    )
    return ok(data={"id": str(link.id)}, message="Teacher-HOD subject link updated")


@router.get("/timetable/all", response_model=dict, dependencies=[Depends(require_permission(TEACHER_READ))])
async def list_all_teacher_timetables(current_user: CurrentUser, db: DB, day_of_week: TimetableDay | None = None):
    items = await service.list_institution_timetable(
        db,
        current_user["institution_id"],
        day_of_week=day_of_week,
    )
    return ok(data=items)


@router.get("/{teacher_id}/timetable", response_model=dict, dependencies=[Depends(require_permission(TEACHER_READ))])
async def list_teacher_timetable(
    teacher_id: str,
    current_user: CurrentUser,
    db: DB,
    day_of_week: TimetableDay | None = None,
):
    await service.assert_can_view_teacher(db, current_user, teacher_id)
    items = await service.list_teacher_timetable(db, teacher_id, day_of_week=day_of_week)
    return ok(data=[TeacherTimetableOut(**item).model_dump() for item in items])


@router.post("/{teacher_id}/timetable", response_model=dict, dependencies=[Depends(require_permission(TEACHER_UPDATE))])
async def create_teacher_timetable(teacher_id: str, payload: TeacherTimetableCreate, db: DB):
    item = await service.create_timetable_entry(db, teacher_id, payload)
    return ok(data={"id": str(item.id)}, message="Timetable entry created")


@router.post("/{teacher_id}/timetable/import", response_model=dict, dependencies=[Depends(require_permission(TEACHER_UPDATE))])
async def import_teacher_timetable(teacher_id: str, db: DB, file: UploadFile = File(...)):
    content = await file.read()
    result = await service.import_timetable_entries(db, teacher_id, file.filename or "upload.csv", content)
    return ok(data=result, message="Timetable import completed")


@router.patch("/timetable/{entry_id}", response_model=dict, dependencies=[Depends(require_permission(TEACHER_UPDATE))])
async def update_teacher_timetable(entry_id: str, payload: TeacherTimetableUpdate, db: DB):
    item = await service.update_timetable_entry(db, entry_id, payload)
    return ok(data={"id": str(item.id)}, message="Timetable entry updated")


@router.patch("/timetable/{entry_id}/reassign", response_model=dict, dependencies=[Depends(require_permission(TEACHER_UPDATE))])
async def reassign_teacher_timetable(entry_id: str, payload: TeacherTimetableReassignRequest, current_user: CurrentUser, db: DB):
    item = await service.reassign_timetable_entry(
        db,
        entry_id,
        str(payload.target_teacher_id),
        current_user["id"],
        current_user["institution_id"],
        current_user["is_superuser"],
    )
    return ok(data={"id": str(item.id), "teacher_id": str(item.teacher_id)}, message="Class reallocated")


@router.delete("/timetable/{entry_id}", response_model=dict, dependencies=[Depends(require_permission(TEACHER_UPDATE))])
async def delete_teacher_timetable(entry_id: str, db: DB):
    await service.delete_timetable_entry(db, entry_id)
    return ok(message="Timetable entry deleted")


@router.get("/self/my-timetable", response_model=dict)
async def my_timetable(current_user: CurrentUser, db: DB):
    teacher = (await db.execute(select(Teacher).where(Teacher.user_id == current_user["id"]))).scalar_one_or_none()
    if not teacher:
        raise NotFoundError("Teacher profile not found for current user")
    items = await service.list_teacher_timetable(db, str(teacher.id))
    return ok(data=[TeacherTimetableOut(**item).model_dump() for item in items])


@router.get("/self/dashboard", response_model=dict)
async def my_dashboard(current_user: CurrentUser, db: DB):
    teacher = (await db.execute(select(Teacher).where(Teacher.user_id == current_user["id"]))).scalar_one_or_none()
    if not teacher:
        raise NotFoundError("Teacher profile not found for current user")
    user = (await db.execute(select(User).where(User.id == teacher.user_id))).scalar_one()
    today = date.today()
    timetable = await service.list_teacher_timetable(db, str(teacher.id))
    today_items = await service.list_teacher_timetable(db, str(teacher.id), session_date=today)
    classes = await service.list_teacher_classes(db, str(teacher.id))
    open_today = [
        item for item in today_items
        if str(item.get("session_status") or "").lower() not in ("closed", "locked")
    ]
    return ok(
        data={
            "teacher": {
                "id": str(teacher.id),
                "user_id": str(teacher.user_id),
                "full_name": user.full_name,
                "email": user.email,
                "employee_code": teacher.employee_code,
                "designation": teacher.designation,
                "joined_at": teacher.joined_at,
            },
            "stats": {
                "assigned_classes": len(classes),
                "weekly_slots": len(timetable),
                "today_classes": len(today_items),
                "pending_attendance": len(open_today),
            },
            "today_classes": [TeacherTimetableOut(**item).model_dump() for item in today_items],
            "assigned_classes": [TeacherClassOut(**item).model_dump() for item in classes],
        }
    )


@router.get("/self/hod-analytics", response_model=dict)
async def my_hod_analytics(current_user: CurrentUser, db: DB, academic_year_id: str | None = None):
    data = await service.get_hod_branch_analytics(db, current_user["id"], academic_year_id)
    return ok(data=data)


@router.get("/self/today-classes", response_model=dict)
async def today_classes(current_user: CurrentUser, db: DB):
    teacher = (await db.execute(select(Teacher).where(Teacher.user_id == current_user["id"]))).scalar_one_or_none()
    if not teacher:
        raise NotFoundError("Teacher profile not found for current user")
    today = date.today()
    items = await service.list_teacher_timetable(db, str(teacher.id), session_date=today)
    return ok(data=[TeacherTimetableOut(**item).model_dump() for item in items])
