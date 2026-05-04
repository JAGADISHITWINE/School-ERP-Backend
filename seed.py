"""
Idempotent seed script — safe to run multiple times:
    python seed.py
"""
import asyncio
from sqlalchemy import select
from app.db.session import AsyncSessionLocal
from app.modules.organizations.model import Organization
from app.modules.institutions.model import Institution
from app.modules.users.model import User
from app.modules.roles.model import Role, Permission, UserRole, RolePermission, Menu
from app.core.security import hash_password
import app.constants.permissions as P

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
]

MENU_DEFS = [
    ("Dashboard",    "/dashboard",          "LayoutDashboard", 1,  None),
    ("Academic",     None,                  "BookOpen",        2,  None),
    ("Courses",      "/academic/courses",   "GraduationCap",   1,  "Academic"),
    ("Branches",     "/academic/branches",  "GitBranch",       2,  "Academic"),
    ("Subjects",     "/academic/subjects",  "BookMarked",      3,  "Academic"),
    ("Classes",      "/academic/classes",   "School",          4,  "Academic"),
    ("Sections",     "/academic/sections",  "Layers",          5,  "Academic"),
    ("Students",     "/students",           "Users",           3,  None),
    ("Teachers",     "/teachers",           "UserCheck",       4,  None),
    ("Attendance",   "/attendance",         "CalendarCheck",   5,  None),
    ("Exams",        "/exams",              "ClipboardList",   6,  None),
    ("Fees",         None,                  "IndianRupee",     7,  None),
    ("Fee Types",    "/fees/types",         "Tags",            1,  "Fees"),
    ("Collect Fee",  "/fees/collect",       "CreditCard",      2,  "Fees"),
    ("Library",      "/library",            "Library",         8,  None),
    ("Settings",     None,                  "Settings",        9,  None),
    ("Organizations","/organizations",      "Building2",       1,  "Settings"),
    ("Institutions", "/institutions",       "Building",        2,  "Settings"),
    ("Roles",        "/settings/roles",     "Shield",          3,  "Settings"),
    ("Users",        "/settings/users",     "UserCog",         4,  "Settings"),
    ("Menus",        "/settings/menus",     "Menu",            5,  "Settings"),
    ("Permissions",  "/settings/perms",     "Key",             6,  "Settings"),
   
]


async def get_one(db, model, *conditions):
    res = await db.execute(select(model).where(*conditions))
    return res.scalar_one_or_none()


async def seed():
    async with AsyncSessionLocal() as db:
        org = await get_one(db, Organization, Organization.slug == "demo-university")
        if not org:
            org = Organization(name="Demo University Group", slug="demo-university", is_active=True)
            db.add(org)
            await db.flush()
        else:
            org.name = "Demo University Group"
            org.is_active = True

        inst = await get_one(db, Institution, Institution.code == "DEC-001")
        if not inst:
            inst = Institution(
                org_id=org.id,
                name="Demo Engineering College",
                code="DEC-001",
                address="123 College Road, Chennai",
                is_active=True,
            )
            db.add(inst)
            await db.flush()
        else:
            inst.org_id = org.id
            inst.name = "Demo Engineering College"
            inst.address = "123 College Road, Chennai"
            inst.is_active = True

        perm_map = {}
        for code, module, action in PERMISSION_DEFS:
            p = await get_one(db, Permission, Permission.code == code)
            if not p:
                p = Permission(code=code, module=module, action=action, description=f"{module} {action}")
                db.add(p)
                await db.flush()
            else:
                p.module = module
                p.action = action
                p.description = f"{module} {action}"
            perm_map[code] = p

        async def get_or_create_role(name: str, slug: str, desc: str):
            r = await get_one(db, Role, Role.slug == slug)
            if not r:
                r = Role(institution_id=inst.id, name=name, slug=slug, description=desc, is_system=True)
                db.add(r)
                await db.flush()
            else:
                r.institution_id = inst.id
                r.name = name
                r.description = desc
                r.is_system = True
            return r

        superadmin_role = await get_or_create_role("Super Admin", "superadmin", "Full access")
        admin_role = await get_or_create_role("Admin", "admin", "Institution admin")
        teacher_role = await get_or_create_role("Teacher", "teacher", "Teaching staff")

        async def ensure_role_perm(role_id, perm_id):
            rp = await get_one(db, RolePermission, RolePermission.role_id == role_id, RolePermission.permission_id == perm_id)
            if not rp:
                db.add(RolePermission(role_id=role_id, permission_id=perm_id))

        for p in perm_map.values():
            await ensure_role_perm(superadmin_role.id, p.id)

        admin_perms = [
            code for code in perm_map
            if code not in (P.ORG_MANAGE, P.INSTITUTION_MANAGE, P.PERMISSION_MANAGE)
        ]
        for code in admin_perms:
            await ensure_role_perm(admin_role.id, perm_map[code].id)

        teacher_perms = [P.ATTENDANCE_MARK, P.ATTENDANCE_READ, P.MARKS_UPLOAD, P.STUDENT_READ]
        for code in teacher_perms:
            await ensure_role_perm(teacher_role.id, perm_map[code].id)

        user = await get_one(db, User, User.email == "admin@erp.com")
        if not user:
            user = User(
                institution_id=inst.id,
                email="admin@erp.com",
                username="admin",
                password_hash=hash_password("Admin@123"),
                full_name="System Administrator",
                is_active=True,
                is_superuser=True,
            )
            db.add(user)
            await db.flush()
        else:
            user.institution_id = inst.id
            user.username = "admin"
            user.full_name = "System Administrator"
            user.is_active = True
            user.is_superuser = True

        ur = await get_one(db, UserRole, UserRole.user_id == user.id, UserRole.role_id == superadmin_role.id)
        if not ur:
            db.add(UserRole(user_id=user.id, role_id=superadmin_role.id))

        menu_label_map = {}
        for label, route, icon, order, parent_label in MENU_DEFS:
            parent_id = menu_label_map[parent_label].id if parent_label else None
            m = await get_one(db, Menu, Menu.label == label, Menu.parent_id == parent_id)
            if not m:
                m = Menu(label=label, route=route, icon=icon, order_no=order, parent_id=parent_id, is_active=True)
                db.add(m)
                await db.flush()
            else:
                m.route = route
                m.icon = icon
                m.order_no = order
                m.parent_id = parent_id
                m.is_active = True
            menu_label_map[label] = m

        await db.commit()
        print("✅ Seed complete (idempotent).")
        print("   Email   : admin@erp.com")
        print("   Password: Admin@123")
        print(f"   Org ID  : {org.id}")
        print(f"   Inst ID : {inst.id}")


if __name__ == "__main__":
    asyncio.run(seed())
