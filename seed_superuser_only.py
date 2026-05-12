"""
Minimal idempotent seed script.

Creates only:
- one required organization shell
- one required institution shell
- one super admin role
- one super user
- permissions assigned to the super admin role
- admin menu tree

Run:
    python seed_superuser_only.py
"""
import asyncio

from sqlalchemy import select

import app.constants.permissions as P
from app.core.security import hash_password
from app.db.session import AsyncSessionLocal
from app.modules.institutions.model import Institution
from app.modules.organizations.model import Organization
from app.modules.roles.model import Menu, Permission, Role, RoleMenu, RolePermission, UserRole
from app.modules.users.model import User


SUPER_USER_EMAIL = "admin@erp.com"
SUPER_USER_USERNAME = "admin"
SUPER_USER_PASSWORD = "Admin@123"

ORG_SLUG = "vidya-learning-trust"
ORG_NAME = "Vidya Learning Trust"
INSTITUTION_CODE = "VIT"
INSTITUTION_NAME = "Vidya Institute of Technology"

PERMISSION_DEFS = [
    (P.USER_CREATE, "users", "create"), (P.USER_READ, "users", "read"),
    (P.USER_UPDATE, "users", "update"), (P.USER_DELETE, "users", "delete"),
    (P.ROLE_CREATE, "roles", "create"), (P.ROLE_READ, "roles", "read"),
    (P.ROLE_UPDATE, "roles", "update"), (P.ROLE_DELETE, "roles", "delete"),
    (P.STUDENT_CREATE, "students", "create"), (P.STUDENT_READ, "students", "read"),
    (P.STUDENT_UPDATE, "students", "update"), (P.STUDENT_DELETE, "students", "delete"),
    (P.TEACHER_CREATE, "teachers", "create"), (P.TEACHER_READ, "teachers", "read"),
    (P.TEACHER_UPDATE, "teachers", "update"), (P.TEACHER_DELETE, "teachers", "delete"),
    (P.COURSE_MANAGE, "academic", "course_manage"),
    (P.BRANCH_MANAGE, "academic", "branch_manage"),
    (P.SUBJECT_MANAGE, "academic", "subject_manage"),
    (P.CLASS_MANAGE, "academic", "class_manage"),
    (P.SECTION_MANAGE, "academic", "section_manage"),
    (P.ACADEMIC_YEAR_MANAGE, "academic", "academic_year_manage"),
    (P.ATTENDANCE_MARK, "attendance", "mark"),
    (P.ATTENDANCE_READ, "attendance", "read"),
    (P.EXAM_CREATE, "exams", "create"), (P.EXAM_MANAGE, "exams", "manage"),
    (P.MARKS_UPLOAD, "marks", "upload"), (P.MARKS_LOCK, "marks", "lock"),
    (P.FEE_MANAGE, "fees", "manage"), (P.FEE_COLLECT, "fees", "collect"),
    (P.LIBRARY_MANAGE, "library", "manage"), (P.LIBRARY_ISSUE, "library", "issue"),
    (P.ORG_MANAGE, "organizations", "manage"),
    (P.INSTITUTION_MANAGE, "institutions", "manage"),
    (P.MENU_MANAGE, "menus", "manage"),
    (P.PERMISSION_MANAGE, "permissions", "manage"),
    (P.ACTIVITY_LOG_READ, "logs", "read"),
    (P.NOTIFICATION_READ, "notifications", "read"),
    (P.NOTIFICATION_MANAGE, "notifications", "manage"),
    (P.PARENT_READ, "parents", "read"),
    (P.ADMIN_BULK_MANAGE, "admin_bulk", "manage"),
]

MENU_DEFS = [
    ("Dashboard", "/dashboard", "LayoutDashboard", 1, None),
    ("Academic", None, "BookOpen", 2, None),
    ("Academic Years", "/academic/years", "CalendarDays", 1, "Academic"),
    ("Courses", "/academic/courses", "GraduationCap", 2, "Academic"),
    ("Branches", "/academic/branches", "GitBranch", 3, "Academic"),
    ("Classes", "/academic/classes", "School", 4, "Academic"),
     ("Subjects", "/academic/subjects", "BookMarked", 5, "Academic"),
    ("Sections", "/academic/sections", "Layers", 6, "Academic"),
    ("Students", None, "Users", 3, None),
    ("Registry", "/students/registry", "Users", 1, "Students"),
    ("Admissions", "/students/admissions", "UserPlus", 2, "Students"),
    ("Academic Records", "/students/academic-records", "History", 3, "Students"),
    ("Promotions", "/students/promotions", "ArrowRight", 4, "Students"),
    ("Guardians", "/students/guardians", "Phone", 5, "Students"),
    ("Documents", "/students/documents", "FileText", 6, "Students"),
    ("Status", "/students/status", "ShieldCheck", 7, "Students"),
    ("Teachers", None, "UserCheck", 4, None),
    ("Teacher Profiles", "/teachers", "UsersRound", 1, "Teachers"),
    ("HOD Linking", "/hod-linking", "Network", 2, "Teachers"),
    ("Teacher Linking", "/teacher-linking", "Link2", 3, "Teachers"),
    ("Class Mentors", "/class-mentors", "UserCheck", 4, "Teachers"),
    ("Timetable", "/timetable", "CalendarClock", 5, "Teachers"),
    ("My Classes", "/classes", "School", 5, None),
    ("Attendance", "/attendance", "CalendarCheck", 6, None),
    ("Materials & Assignments", "/teacher-content", "FileUp", 7, None),
    ("Exams", "/exams", "ClipboardList", 8, None),
    ("Fees", None, "IndianRupee", 9, None),
    ("Fee Types", "/fees/types", "Tags", 1, "Fees"),
    ("Collect Fee", "/fees/collect", "CreditCard", 2, "Fees"),
    ("Reports", "/reports", "BarChart3", 10, None),
    ("Student Complete Report", "/student-complete-report", "FileText", 11, None),
    ("Notifications", "/notifications", "Bell", 12, None),
    ("Library", "/library", "Library", 13, None),
    ("Settings", None, "Settings", 14, None),
    ("Organizations", "/organizations", "Building2", 1, "Settings"),
    ("Institutions", "/institutions", "Building", 2, "Settings"),
    ("Roles", "/settings/roles", "Shield", 3, "Settings"),
    ("Users", "/settings/users", "UserCog", 4, "Settings"),
    ("Menus", "/settings/menus", "Menu", 5, "Settings"),
    ("Permissions", "/settings/perms", "Key", 6, "Settings"),
]


async def get_one(db, model, *conditions):
    result = await db.execute(select(model).where(*conditions))
    return result.scalar_one_or_none()


async def ensure_organization(db):
    org = await get_one(db, Organization, Organization.slug == ORG_SLUG)
    if not org:
        org = Organization(name=ORG_NAME, slug=ORG_SLUG, is_active=True)
        db.add(org)
        await db.flush()
    else:
        org.name = ORG_NAME
        org.is_active = True
    return org


async def ensure_institution(db, org):
    institution = await get_one(db, Institution, Institution.code == INSTITUTION_CODE)
    if not institution:
        institution = Institution(
            org_id=org.id,
            name=INSTITUTION_NAME,
            code=INSTITUTION_CODE,
            address="System bootstrap institution",
            is_active=True,
        )
        db.add(institution)
        await db.flush()
    else:
        institution.org_id = org.id
        institution.name = INSTITUTION_NAME
        institution.address = "System bootstrap institution"
        institution.is_active = True
    return institution


async def ensure_superadmin_role(db, institution):
    role = await get_one(db, Role, Role.slug == "superadmin")
    if not role:
        role = Role(
            institution_id=institution.id,
            name="Super Admin",
            slug="superadmin",
            description="Full system access",
            is_system=True,
        )
        db.add(role)
        await db.flush()
    else:
        role.institution_id = institution.id
        role.name = "Super Admin"
        role.description = "Full system access"
        role.is_system = True
    return role


async def ensure_super_user(db, institution, role):
    user = await get_one(db, User, User.email == SUPER_USER_EMAIL)
    if not user:
        user = User(
            institution_id=institution.id,
            email=SUPER_USER_EMAIL,
            username=SUPER_USER_USERNAME,
            password_hash=hash_password(SUPER_USER_PASSWORD),
            full_name="System Administrator",
            is_active=True,
            is_superuser=True,
        )
        db.add(user)
        await db.flush()
    else:
        user.institution_id = institution.id
        user.username = SUPER_USER_USERNAME
        user.password_hash = hash_password(SUPER_USER_PASSWORD)
        user.full_name = "System Administrator"
        user.is_active = True
        user.is_superuser = True

    user_role = await get_one(db, UserRole, UserRole.user_id == user.id, UserRole.role_id == role.id)
    if not user_role:
        db.add(UserRole(user_id=user.id, role_id=role.id))
    return user


async def ensure_permissions(db, role):
    permission_map = {}
    for code, module, action in PERMISSION_DEFS:
        permission = await get_one(db, Permission, Permission.code == code)
        description = f"{module} {action}"
        if not permission:
            permission = Permission(
                code=code,
                module=module,
                action=action,
                description=description,
            )
            db.add(permission)
            await db.flush()
        else:
            permission.module = module
            permission.action = action
            permission.description = description

        permission_map[code] = permission

        role_permission = await get_one(
            db,
            RolePermission,
            RolePermission.role_id == role.id,
            RolePermission.permission_id == permission.id,
        )
        if not role_permission:
            db.add(RolePermission(role_id=role.id, permission_id=permission.id))

    return permission_map


async def ensure_menus(db, role):
    menu_label_map = {}
    for label, route, icon, order_no, parent_label in MENU_DEFS:
        parent_id = menu_label_map[parent_label].id if parent_label else None
        menu = await get_one(db, Menu, Menu.label == label, Menu.parent_id == parent_id)
        if not menu:
            menu = Menu(
                parent_id=parent_id,
                label=label,
                route=route,
                icon=icon,
                order_no=order_no,
                is_active=True,
            )
            db.add(menu)
            await db.flush()
        else:
            menu.parent_id = parent_id
            menu.route = route
            menu.icon = icon
            menu.order_no = order_no
            menu.is_active = True
        menu_label_map[label] = menu

        role_menu = await get_one(db, RoleMenu, RoleMenu.role_id == role.id, RoleMenu.menu_id == menu.id)
        if not role_menu:
            db.add(RoleMenu(role_id=role.id, menu_id=menu.id))

    return menu_label_map


async def seed():
    async with AsyncSessionLocal() as db:
        org = await ensure_organization(db)
        institution = await ensure_institution(db, org)
        role = await ensure_superadmin_role(db, institution)
        await ensure_super_user(db, institution, role)
        await ensure_permissions(db, role)
        await ensure_menus(db, role)
        await db.commit()

    print("Minimal super user seed complete.")
    print(f"Email   : {SUPER_USER_EMAIL}")
    print(f"Username: {SUPER_USER_USERNAME}")
    print(f"Password: {SUPER_USER_PASSWORD}")


if __name__ == "__main__":
    asyncio.run(seed())
