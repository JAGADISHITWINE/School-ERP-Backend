"""
Idempotent seed script — safe to run multiple times:
    python seed.py
"""
import asyncio
from datetime import date, datetime, time, timedelta, timezone
from sqlalchemy import delete, select
from app.db.session import AsyncSessionLocal
from app.modules.organizations.model import Organization
from app.modules.institutions.model import Institution
from app.modules.users.model import User
from app.modules.roles.model import Role, Permission, UserRole, RolePermission, Menu, RoleMenu
from app.modules.academic.model import AcademicYear, Course, Branch, Class, Section, Subject
from app.modules.students.model import Student, StudentAcademicRecord, StudentStatus, StudentDocument
from app.modules.teachers.model import (
    Teacher,
    TeacherClass,
    TeacherSubject,
    TeacherTimetable,
    TimetableDay,
    HODLink,
    TeacherHODSubjectLink,
)
from app.modules.attendance.model import AttendanceSession, AttendanceRecord, AttendanceStatus, SessionStatus
from app.modules.exams.model import Exam, ExamSubject, Mark, ExamWorkflow
from app.modules.fees.model import FeeType, FeeStructure, StudentFee, FeePayment, FeeStatus
from app.modules.library.model import Book, BookIssue, IssueStatus
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
    (P.ACTIVITY_LOG_READ, "logs", "read"),
    (P.NOTIFICATION_READ, "notifications", "read"),
    (P.NOTIFICATION_MANAGE, "notifications", "manage"),
    (P.PARENT_READ, "parents", "read"),
    (P.ADMIN_BULK_MANAGE, "admin_bulk", "manage"),
]

MENU_DEFS = [
    ("Dashboard",    "/dashboard",          "LayoutDashboard", 1,  None),
    ("Academic",     None,                  "BookOpen",        2,  None),
    ("Academic Years","/academic/years",    "CalendarDays",    1,  "Academic"),
    ("Courses",      "/academic/courses",   "GraduationCap",   2,  "Academic"),
    ("Branches",     "/academic/branches",  "GitBranch",       3,  "Academic"),
    ("Subjects",     "/academic/subjects",  "BookMarked",      4,  "Academic"),
    ("Classes",      "/academic/classes",   "School",          5,  "Academic"),
    ("Sections",     "/academic/sections",  "Layers",          6,  "Academic"),
    ("Students",     None,                  "Users",           3,  None),
    ("Registry",     "/students/registry",  "Users",           1,  "Students"),
    ("Admissions",   "/students/admissions","UserPlus",        2,  "Students"),
    ("Academic Records","/students/academic-records","History",3,  "Students"),
    ("Promotions",   "/students/promotions","ArrowRight",      4,  "Students"),
    ("Guardians",    "/students/guardians", "Phone",           5,  "Students"),
    ("Documents",    "/students/documents", "FileText",        6,  "Students"),
    ("Status",       "/students/status",    "ShieldCheck",     7,  "Students"),
    ("Teachers",     None,                  "UserCheck",       4,  None),
    ("Teacher Profiles","/teachers",        "UsersRound",      1,  "Teachers"),
    ("HOD Linking",  "/hod-linking",        "Network",         2,  "Teachers"),
    ("Teacher Linking","/teacher-linking",  "Link2",           3,  "Teachers"),
    ("Class Mentors","/class-mentors",      "UserCheck",       4,  "Teachers"),
    ("Timetable",    "/timetable",          "CalendarClock",   5,  "Teachers"),
    ("My Classes",   "/classes",            "School",          5,  None),
    ("Attendance",   "/attendance",         "CalendarCheck",   6,  None),
    ("Materials & Assignments","/teacher-content","FileUp",    7,  None),
    ("Exams",        "/exams",              "ClipboardList",   8,  None),
    ("Fees",         None,                  "IndianRupee",     9,  None),
    ("Fee Types",    "/fees/types",         "Tags",            1,  "Fees"),
    ("Collect Fee",  "/fees/collect",       "CreditCard",      2,  "Fees"),
    ("Reports",      "/reports",            "BarChart3",       10, None),
    ("Student Complete Report","/student-complete-report","FileText",11, None),
    ("Notifications","/notifications",      "Bell",            12, None),
    ("Library",      "/library",            "Library",         13, None),
    ("Settings",     None,                  "Settings",        14, None),
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


async def ensure_user(db, institution_id, role_id, *, email, username, full_name, phone=None, password="Demo@123"):
    user = await get_one(db, User, User.email == email)
    if not user:
        user = User(
            institution_id=institution_id,
            email=email,
            username=username,
            password_hash=hash_password(password),
            full_name=full_name,
            phone=phone,
            is_active=True,
            is_superuser=False,
        )
        db.add(user)
        await db.flush()
    else:
        user.institution_id = institution_id
        user.username = username
        user.password_hash = hash_password(password)
        user.full_name = full_name
        user.phone = phone
        user.is_active = True

    user_role = await get_one(db, UserRole, UserRole.user_id == user.id, UserRole.role_id == role_id)
    if not user_role:
        db.add(UserRole(user_id=user.id, role_id=role_id))
    return user


async def ensure_academic_year(db, institution_id, label, start_date, end_date, is_current=False):
    year = await get_one(
        db,
        AcademicYear,
        AcademicYear.institution_id == institution_id,
        AcademicYear.label == label,
    )
    if not year:
        year = AcademicYear(
            institution_id=institution_id,
            label=label,
            start_date=start_date,
            end_date=end_date,
            is_current=is_current,
            is_active=True,
        )
        db.add(year)
        await db.flush()
    else:
        year.start_date = start_date
        year.end_date = end_date
        year.is_current = is_current
        year.is_active = True
    return year


async def ensure_course(db, institution_id, name, code, level, duration_years):
    course = await get_one(db, Course, Course.code == code)
    if not course:
        course = Course(
            institution_id=institution_id,
            name=name,
            code=code,
            level=level,
            duration_years=duration_years,
            is_active=True,
        )
        db.add(course)
        await db.flush()
    else:
        course.institution_id = institution_id
        course.name = name
        course.level = level
        course.duration_years = duration_years
        course.is_active = True
    return course


async def ensure_branch(db, course_id, name, code):
    branch = await get_one(db, Branch, Branch.course_id == course_id, Branch.code == code)
    if not branch:
        branch = Branch(course_id=course_id, name=name, code=code, is_active=True)
        db.add(branch)
        await db.flush()
    else:
        branch.name = name
        branch.is_active = True
    return branch


async def ensure_class(db, course_id, branch_id, academic_year_id, name, year_no, semester, intake_capacity=60):
    class_ = await get_one(
        db,
        Class,
        Class.course_id == course_id,
        Class.branch_id == branch_id,
        Class.academic_year_id == academic_year_id,
        Class.name == name,
    )
    if not class_:
        class_ = Class(
            course_id=course_id,
            branch_id=branch_id,
            academic_year_id=academic_year_id,
            name=name,
            year_no=year_no,
            semester=semester,
            intake_capacity=intake_capacity,
        )
        db.add(class_)
        await db.flush()
    else:
        class_.year_no = year_no
        class_.semester = semester
        class_.intake_capacity = intake_capacity
    return class_


async def ensure_section(db, class_id, name, max_strength=60):
    section = await get_one(db, Section, Section.class_id == class_id, Section.name == name)
    if not section:
        section = Section(class_id=class_id, name=name, max_strength=max_strength)
        db.add(section)
        await db.flush()
    else:
        section.max_strength = max_strength
    return section


async def ensure_subject(db, course_id, class_id, branch_id, academic_year_id, semester, name, code, credits):
    subject = await get_one(db, Subject, Subject.class_id == class_id, Subject.code == code)
    if not subject:
        subject = Subject(
            course_id=course_id,
            class_id=class_id,
            branch_id=branch_id,
            academic_year_id=academic_year_id,
            semester=semester,
            name=name,
            code=code,
            credits=credits,
            is_active=True,
        )
        db.add(subject)
        await db.flush()
    else:
        subject.course_id = course_id
        subject.branch_id = branch_id
        subject.academic_year_id = academic_year_id
        subject.semester = semester
        subject.name = name
        subject.credits = credits
        subject.is_active = True
    return subject


async def ensure_teacher(db, institution_id, teacher_role_id, *, email, username, full_name, employee_code, designation, phone):
    user = await ensure_user(
        db,
        institution_id,
        teacher_role_id,
        email=email,
        username=username,
        full_name=full_name,
        phone=phone,
    )
    teacher = await get_one(db, Teacher, Teacher.employee_code == employee_code)
    if not teacher:
        teacher = Teacher(
            user_id=user.id,
            employee_code=employee_code,
            designation=designation,
            joined_at=date(2021, 6, 14),
        )
        db.add(teacher)
        await db.flush()
    else:
        teacher.user_id = user.id
        teacher.designation = designation
        teacher.joined_at = date(2021, 6, 14)
    return teacher


async def ensure_student(db, institution_id, student_role_id, *, email, username, full_name, roll_number, dob, gender, guardian, guardian_phone, guardian_email, section_id, branch_id, academic_year_id):
    user = await ensure_user(
        db,
        institution_id,
        student_role_id,
        email=email,
        username=username,
        full_name=full_name,
        phone=guardian_phone,
    )
    student = await get_one(db, Student, Student.roll_number == roll_number)
    if not student:
        student = Student(
            user_id=user.id,
            roll_number=roll_number,
            date_of_birth=dob,
            gender=gender,
            guardian_name=guardian,
            guardian_phone=guardian_phone,
            guardian_email=guardian_email,
        )
        db.add(student)
        await db.flush()
    else:
        student.user_id = user.id
        student.date_of_birth = dob
        student.gender = gender
        student.guardian_name = guardian
        student.guardian_phone = guardian_phone
        student.guardian_email = guardian_email

    record = await get_one(
        db,
        StudentAcademicRecord,
        StudentAcademicRecord.student_id == student.id,
        StudentAcademicRecord.academic_year_id == academic_year_id,
        StudentAcademicRecord.section_id == section_id,
    )
    if not record:
        record = StudentAcademicRecord(
            student_id=student.id,
            section_id=section_id,
            branch_id=branch_id,
            academic_year_id=academic_year_id,
            status=StudentStatus.ACTIVE,
            enrolled_at=datetime(2026, 7, 1, tzinfo=timezone.utc),
        )
        db.add(record)
    else:
        record.branch_id = branch_id
        record.status = StudentStatus.ACTIVE
        record.exited_at = None
    return student


async def ensure_teacher_class(db, teacher_id, class_id):
    link = await get_one(db, TeacherClass, TeacherClass.teacher_id == teacher_id, TeacherClass.class_id == class_id)
    if not link:
        db.add(TeacherClass(teacher_id=teacher_id, class_id=class_id))


async def ensure_student_document(db, student_id, *, document_type, title, file_name, status="verified", remarks=None):
    item = await get_one(
        db,
        StudentDocument,
        StudentDocument.student_id == student_id,
        StudentDocument.document_type == document_type,
        StudentDocument.title == title,
    )
    if not item:
        item = StudentDocument(
            student_id=student_id,
            document_type=document_type,
            title=title,
            file_name=file_name,
            status=status,
            remarks=remarks,
        )
        db.add(item)
    else:
        item.file_name = file_name
        item.status = status
        item.remarks = remarks
    return item


async def ensure_teacher_subject(db, teacher_id, subject_id, section_id, academic_year_id):
    link = await get_one(
        db,
        TeacherSubject,
        TeacherSubject.teacher_id == teacher_id,
        TeacherSubject.subject_id == subject_id,
        TeacherSubject.section_id == section_id,
        TeacherSubject.academic_year_id == academic_year_id,
    )
    if not link:
        db.add(TeacherSubject(
            teacher_id=teacher_id,
            subject_id=subject_id,
            section_id=section_id,
            academic_year_id=academic_year_id,
        ))


async def ensure_timetable(db, teacher_id, class_id, section_id, subject_id, academic_year_id, day, start, end, room):
    entry = await get_one(
        db,
        TeacherTimetable,
        TeacherTimetable.teacher_id == teacher_id,
        TeacherTimetable.day_of_week == day,
        TeacherTimetable.start_time == start,
        TeacherTimetable.section_id == section_id,
    )
    if not entry:
        entry = TeacherTimetable(
            teacher_id=teacher_id,
            class_id=class_id,
            section_id=section_id,
            subject_id=subject_id,
            academic_year_id=academic_year_id,
            day_of_week=day,
            start_time=start,
            end_time=end,
            room_no=room,
            is_active=True,
        )
        db.add(entry)
        await db.flush()
    else:
        entry.class_id = class_id
        entry.subject_id = subject_id
        entry.academic_year_id = academic_year_id
        entry.end_time = end
        entry.room_no = room
        entry.is_active = True
    return entry


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
            with db.no_autoflush:
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
        hod_role = await get_or_create_role("HOD", "hod", "Head of department")
        teacher_role = await get_or_create_role("Teacher", "teacher", "Teaching staff")
        accountant_role = await get_or_create_role("Accountant", "accountant", "Accounts and fee collection")
        student_role = await get_or_create_role("Student", "student", "Student account")
        parent_role = await get_or_create_role("Parent", "parent", "Parent portal access")

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

        teacher_perms = [P.TEACHER_READ, P.ATTENDANCE_MARK, P.ATTENDANCE_READ, P.MARKS_UPLOAD, P.STUDENT_READ, P.NOTIFICATION_READ]
        for code in teacher_perms:
            await ensure_role_perm(teacher_role.id, perm_map[code].id)

        hod_perms = [
            P.TEACHER_READ, P.TEACHER_UPDATE, P.STUDENT_READ,
            P.ATTENDANCE_READ, P.MARKS_UPLOAD, P.COURSE_MANAGE,
            P.BRANCH_MANAGE, P.SUBJECT_MANAGE, P.CLASS_MANAGE, P.SECTION_MANAGE,
            P.ACADEMIC_YEAR_MANAGE, P.NOTIFICATION_READ,
        ]
        for code in hod_perms:
            await ensure_role_perm(hod_role.id, perm_map[code].id)

        accountant_perms = [P.STUDENT_READ, P.FEE_MANAGE, P.FEE_COLLECT, P.NOTIFICATION_READ]
        for code in accountant_perms:
            await ensure_role_perm(accountant_role.id, perm_map[code].id)

        parent_perms = [P.PARENT_READ]
        for code in parent_perms:
            await ensure_role_perm(parent_role.id, perm_map[code].id)

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
            user.password_hash = hash_password("Admin@123")
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

        async def ensure_role_menu(role_id, menu_label):
            menu = menu_label_map.get(menu_label)
            if not menu:
                return
            rm = await get_one(db, RoleMenu, RoleMenu.role_id == role_id, RoleMenu.menu_id == menu.id)
            if not rm:
                db.add(RoleMenu(role_id=role_id, menu_id=menu.id))

        full_menu_labels = [label for label, *_ in MENU_DEFS]
        admin_menu_labels = [
            label for label, *_ in MENU_DEFS
            if label not in ("Organizations", "Permissions")
        ]
        teacher_menu_labels = [
            "Dashboard",
            "My Classes",
            "Timetable",
            "Attendance",
            "Materials & Assignments",
            "Exams",
            "Reports",
            "Student Complete Report",
            "Notifications",
        ]
        hod_menu_labels = [
            "Dashboard",
            "Academic",
            "Courses",
            "Branches",
            "Subjects",
            "Classes",
            "Sections",
            "Students",
            "Registry",
            "Academic Records",
            "Teachers",
            "Teacher Linking",
            "Class Mentors",
            "Timetable",
            "Attendance",
            "Materials & Assignments",
            "Exams",
            "Reports",
            "Student Complete Report",
            "Notifications",
        ]
        accountant_menu_labels = ["Dashboard", "Students", "Registry", "Fees", "Fee Types", "Collect Fee", "Reports", "Notifications"]

        managed_role_ids = [
            superadmin_role.id,
            admin_role.id,
            teacher_role.id,
            hod_role.id,
            accountant_role.id,
            parent_role.id,
        ]
        await db.execute(delete(RoleMenu).where(RoleMenu.role_id.in_(managed_role_ids)))

        for label in full_menu_labels:
            await ensure_role_menu(superadmin_role.id, label)
        for label in admin_menu_labels:
            await ensure_role_menu(admin_role.id, label)
        for label in teacher_menu_labels:
            await ensure_role_menu(teacher_role.id, label)
        for label in hod_menu_labels:
            await ensure_role_menu(hod_role.id, label)
        for label in accountant_menu_labels:
            await ensure_role_menu(accountant_role.id, label)

        current_year = await ensure_academic_year(
            db, inst.id, "2026-27", date(2026, 7, 1), date(2027, 6, 30), True
        )
        previous_year = await ensure_academic_year(
            db, inst.id, "2025-26", date(2025, 7, 1), date(2026, 6, 30), False
        )

        btech = await ensure_course(db, inst.id, "Bachelor of Technology", "BTECH", "UG", 4)
        mtech = await ensure_course(db, inst.id, "Master of Technology", "MTECH", "PG", 2)

        cse = await ensure_branch(db, btech.id, "Computer Science and Engineering", "CSE")
        ece = await ensure_branch(db, btech.id, "Electronics and Communication Engineering", "ECE")
        ds = await ensure_branch(db, mtech.id, "Data Science", "DS")

        cse_sem3 = await ensure_class(db, btech.id, cse.id, current_year.id, "CSE Second Year - Semester 3", 2, 3, 72)
        cse_sem5 = await ensure_class(db, btech.id, cse.id, current_year.id, "CSE Third Year - Semester 5", 3, 5, 68)
        ece_sem3 = await ensure_class(db, btech.id, ece.id, current_year.id, "ECE Second Year - Semester 3", 2, 3, 64)
        ds_sem1 = await ensure_class(db, mtech.id, ds.id, current_year.id, "M.Tech DS First Year - Semester 1", 1, 1, 30)

        cse_a = await ensure_section(db, cse_sem3.id, "A", 60)
        cse_b = await ensure_section(db, cse_sem3.id, "B", 60)
        cse5_a = await ensure_section(db, cse_sem5.id, "A", 60)
        ece_a = await ensure_section(db, ece_sem3.id, "A", 55)
        ds_a = await ensure_section(db, ds_sem1.id, "A", 30)

        subjects = {
            "dbms": await ensure_subject(db, btech.id, cse_sem3.id, cse.id, current_year.id, 3, "Database Management Systems", "CSE301", 4),
            "os": await ensure_subject(db, btech.id, cse_sem3.id, cse.id, current_year.id, 3, "Operating Systems", "CSE302", 4),
            "ds": await ensure_subject(db, btech.id, cse_sem3.id, cse.id, current_year.id, 3, "Data Structures and Algorithms", "CSE303", 4),
            "web": await ensure_subject(db, btech.id, cse_sem5.id, cse.id, current_year.id, 5, "Full Stack Web Development", "CSE501", 3),
            "ai": await ensure_subject(db, btech.id, cse_sem5.id, cse.id, current_year.id, 5, "Artificial Intelligence", "CSE502", 4),
            "signals": await ensure_subject(db, btech.id, ece_sem3.id, ece.id, current_year.id, 3, "Signals and Systems", "ECE301", 4),
            "circuits": await ensure_subject(db, btech.id, ece_sem3.id, ece.id, current_year.id, 3, "Analog Circuits", "ECE302", 4),
            "ml": await ensure_subject(db, mtech.id, ds_sem1.id, ds.id, current_year.id, 1, "Machine Learning Foundations", "DS501", 4),
        }

        teachers = {
            "hod_cse": await ensure_teacher(
                db, inst.id, hod_role.id,
                email="meera.iyer@demo.edu", username="meera.iyer", full_name="Dr. Meera Iyer",
                employee_code="DEC-FAC-1001", designation="Professor & HOD - CSE", phone="9876501001",
            ),
            "teacher_db": await ensure_teacher(
                db, inst.id, teacher_role.id,
                email="arjun.nair@demo.edu", username="arjun.nair", full_name="Arjun Nair",
                employee_code="DEC-FAC-1002", designation="Assistant Professor - CSE", phone="9876501002",
            ),
            "teacher_os": await ensure_teacher(
                db, inst.id, teacher_role.id,
                email="priya.menon@demo.edu", username="priya.menon", full_name="Priya Menon",
                employee_code="DEC-FAC-1003", designation="Assistant Professor - CSE", phone="9876501003",
            ),
            "hod_ece": await ensure_teacher(
                db, inst.id, hod_role.id,
                email="ravi.kumar@demo.edu", username="ravi.kumar", full_name="Dr. Ravi Kumar",
                employee_code="DEC-FAC-2001", designation="Professor & HOD - ECE", phone="9876502001",
            ),
            "teacher_ece": await ensure_teacher(
                db, inst.id, teacher_role.id,
                email="ananya.rao@demo.edu", username="ananya.rao", full_name="Ananya Rao",
                employee_code="DEC-FAC-2002", designation="Assistant Professor - ECE", phone="9876502002",
            ),
        }

        await ensure_user(
            db, inst.id, accountant_role.id,
            email="kavitha.accounts@demo.edu",
            username="kavitha.accounts",
            full_name="Kavitha Srinivasan",
            phone="9876503001",
        )

        class_subject_teacher = [
            (teachers["teacher_db"], cse_sem3, cse_a, subjects["dbms"], "CS-201", TimetableDay.MONDAY, time(9, 0), time(9, 55)),
            (teachers["teacher_os"], cse_sem3, cse_a, subjects["os"], "CS-201", TimetableDay.MONDAY, time(10, 0), time(10, 55)),
            (teachers["teacher_db"], cse_sem3, cse_b, subjects["dbms"], "CS-202", TimetableDay.TUESDAY, time(9, 0), time(9, 55)),
            (teachers["teacher_os"], cse_sem3, cse_b, subjects["ds"], "CS-202", TimetableDay.TUESDAY, time(11, 0), time(11, 55)),
            (teachers["hod_cse"], cse_sem5, cse5_a, subjects["ai"], "AI-Lab", TimetableDay.WEDNESDAY, time(10, 0), time(10, 55)),
            (teachers["teacher_db"], cse_sem5, cse5_a, subjects["web"], "Lab-3", TimetableDay.THURSDAY, time(14, 0), time(15, 30)),
            (teachers["hod_ece"], ece_sem3, ece_a, subjects["signals"], "EC-101", TimetableDay.MONDAY, time(9, 0), time(9, 55)),
            (teachers["teacher_ece"], ece_sem3, ece_a, subjects["circuits"], "EC-102", TimetableDay.WEDNESDAY, time(11, 0), time(11, 55)),
            (teachers["hod_cse"], ds_sem1, ds_a, subjects["ml"], "DS-Research", TimetableDay.FRIDAY, time(10, 0), time(11, 30)),
        ]

        timetable_entries = []
        for teacher, class_, section, subject, room, day, start, end in class_subject_teacher:
            await ensure_teacher_class(db, teacher.id, class_.id)
            await ensure_teacher_subject(db, teacher.id, subject.id, section.id, current_year.id)
            timetable_entries.append(await ensure_timetable(
                db, teacher.id, class_.id, section.id, subject.id, current_year.id, day, start, end, room
            ))

        hod_cse_link = await get_one(db, HODLink, HODLink.hod_teacher_id == teachers["hod_cse"].id, HODLink.branch_id == cse.id)
        if not hod_cse_link:
            hod_cse_link = HODLink(hod_teacher_id=teachers["hod_cse"].id, institution_id=inst.id, course_id=btech.id, branch_id=cse.id)
            db.add(hod_cse_link)
            await db.flush()
        hod_ece_link = await get_one(db, HODLink, HODLink.hod_teacher_id == teachers["hod_ece"].id, HODLink.branch_id == ece.id)
        if not hod_ece_link:
            hod_ece_link = HODLink(hod_teacher_id=teachers["hod_ece"].id, institution_id=inst.id, course_id=btech.id, branch_id=ece.id)
            db.add(hod_ece_link)
            await db.flush()

        for teacher, hod_link, subject in [
            (teachers["teacher_db"], hod_cse_link, subjects["dbms"]),
            (teachers["teacher_os"], hod_cse_link, subjects["os"]),
            (teachers["teacher_os"], hod_cse_link, subjects["ds"]),
            (teachers["teacher_ece"], hod_ece_link, subjects["circuits"]),
        ]:
            link = await get_one(
                db,
                TeacherHODSubjectLink,
                TeacherHODSubjectLink.teacher_id == teacher.id,
                TeacherHODSubjectLink.hod_link_id == hod_link.id,
                TeacherHODSubjectLink.subject_id == subject.id,
            )
            if not link:
                db.add(TeacherHODSubjectLink(teacher_id=teacher.id, hod_link_id=hod_link.id, subject_id=subject.id))

        student_seed = [
            ("Ananya Sharma", "DEC26CSEA001", "ananya.sharma@student.demo.edu", "ananya.sharma", date(2007, 4, 12), "female", "Rajesh Sharma", "9000010001", cse_a, cse),
            ("Rohan Verma", "DEC26CSEA002", "rohan.verma@student.demo.edu", "rohan.verma", date(2006, 11, 3), "male", "Neeta Verma", "9000010002", cse_a, cse),
            ("Ishaan Patel", "DEC26CSEA003", "ishaan.patel@student.demo.edu", "ishaan.patel", date(2007, 1, 22), "male", "Kiran Patel", "9000010003", cse_a, cse),
            ("Diya Nair", "DEC26CSEA004", "diya.nair@student.demo.edu", "diya.nair", date(2007, 8, 5), "female", "Suresh Nair", "9000010004", cse_a, cse),
            ("Kabir Khan", "DEC26CSEA005", "kabir.khan@student.demo.edu", "kabir.khan", date(2006, 12, 19), "male", "Farah Khan", "9000010005", cse_a, cse),
            ("Megha Rao", "DEC26CSEB001", "megha.rao@student.demo.edu", "megha.rao", date(2007, 2, 14), "female", "Vikram Rao", "9000010006", cse_b, cse),
            ("Siddharth Iyer", "DEC26CSEB002", "siddharth.iyer@student.demo.edu", "siddharth.iyer", date(2006, 10, 9), "male", "Latha Iyer", "9000010007", cse_b, cse),
            ("Nisha Thomas", "DEC26CSEB003", "nisha.thomas@student.demo.edu", "nisha.thomas", date(2007, 6, 30), "female", "Mathew Thomas", "9000010008", cse_b, cse),
            ("Aditya Bose", "DEC26CSE5A001", "aditya.bose@student.demo.edu", "aditya.bose", date(2005, 9, 18), "male", "Mala Bose", "9000010009", cse5_a, cse),
            ("Sneha Kulkarni", "DEC26CSE5A002", "sneha.kulkarni@student.demo.edu", "sneha.kulkarni", date(2005, 7, 24), "female", "Prakash Kulkarni", "9000010010", cse5_a, cse),
            ("Varun Reddy", "DEC26ECEA001", "varun.reddy@student.demo.edu", "varun.reddy", date(2007, 3, 15), "male", "Madhavi Reddy", "9000010011", ece_a, ece),
            ("Aisha Rahman", "DEC26ECEA002", "aisha.rahman@student.demo.edu", "aisha.rahman", date(2007, 5, 2), "female", "Sameer Rahman", "9000010012", ece_a, ece),
            ("Harini Subramanian", "DEC26ECEA003", "harini.subramanian@student.demo.edu", "harini.subramanian", date(2006, 12, 7), "female", "Gopal Subramanian", "9000010013", ece_a, ece),
            ("Joel Mathew", "DEC26DSA001", "joel.mathew@student.demo.edu", "joel.mathew", date(2003, 1, 11), "male", "Mary Mathew", "9000010014", ds_a, ds),
            ("Tara Singh", "DEC26DSA002", "tara.singh@student.demo.edu", "tara.singh", date(2003, 8, 21), "female", "Amandeep Singh", "9000010015", ds_a, ds),
        ]

        students = []
        for full_name, roll, email, username, dob, gender, guardian, guardian_phone, section, branch in student_seed:
            guardian_email = f"{guardian.lower().replace(' ', '.')}@parent.demo.edu"
            parent_username = guardian.lower().replace(" ", ".")
            await ensure_user(
                db,
                inst.id,
                parent_role.id,
                email=guardian_email,
                username=f"parent.{parent_username}",
                full_name=guardian,
                phone=guardian_phone,
                password="Demo@123",
            )
            students.append(await ensure_student(
                db, inst.id, student_role.id,
                email=email, username=username, full_name=full_name, roll_number=roll,
                dob=dob, gender=gender, guardian=guardian, guardian_phone=guardian_phone, guardian_email=guardian_email,
                section_id=section.id, branch_id=branch.id, academic_year_id=current_year.id,
            ))

        for student in students:
            await ensure_student_document(
                db,
                student.id,
                document_type="identity",
                title="Student Photo",
                file_name=f"{student.roll_number.lower()}-photo.jpg",
                status="verified",
                remarks="Demo verified document",
            )
            await ensure_student_document(
                db,
                student.id,
                document_type="academic",
                title="Previous Marks Memo",
                file_name=f"{student.roll_number.lower()}-marks.pdf",
                status="pending" if str(student.roll_number).endswith("003") else "verified",
                remarks="Awaiting original verification" if str(student.roll_number).endswith("003") else "Demo verified document",
            )

        attendance_date = date(2026, 7, 6)
        for idx, entry in enumerate(timetable_entries[:5]):
            session = await get_one(
                db,
                AttendanceSession,
                AttendanceSession.section_id == entry.section_id,
                AttendanceSession.subject_id == entry.subject_id,
                AttendanceSession.session_date == attendance_date + timedelta(days=idx),
                AttendanceSession.timetable_id == entry.id,
            )
            if not session:
                session = AttendanceSession(
                    section_id=entry.section_id,
                    subject_id=entry.subject_id,
                    teacher_id=entry.teacher_id,
                    timetable_id=entry.id,
                    academic_year_id=current_year.id,
                    session_date=attendance_date + timedelta(days=idx),
                    status=SessionStatus.CLOSED,
                    approved_by=user.id,
                    approved_at=datetime.now(timezone.utc),
                )
                db.add(session)
                await db.flush()
            section_students = [
                student for student in students
                if await get_one(
                    db,
                    StudentAcademicRecord,
                    StudentAcademicRecord.student_id == student.id,
                    StudentAcademicRecord.section_id == entry.section_id,
                    StudentAcademicRecord.academic_year_id == current_year.id,
                )
            ]
            for student_index, student in enumerate(section_students):
                record = await get_one(db, AttendanceRecord, AttendanceRecord.session_id == session.id, AttendanceRecord.student_id == student.id)
                status = AttendanceStatus.PRESENT
                if student_index == 2:
                    status = AttendanceStatus.LATE
                elif student_index == 4:
                    status = AttendanceStatus.ABSENT
                if not record:
                    db.add(AttendanceRecord(
                        session_id=session.id,
                        student_id=student.id,
                        status=status,
                        remarks="Demo attendance entry",
                    ))
                else:
                    record.status = status
                    record.remarks = "Demo attendance entry"

        exam = await get_one(db, Exam, Exam.institution_id == inst.id, Exam.name == "Cycle Test 1 - July 2026")
        if not exam:
            exam = Exam(
                institution_id=inst.id,
                academic_year_id=current_year.id,
                name="Cycle Test 1 - July 2026",
                exam_type="unit_test",
                workflow_status=ExamWorkflow.SUBMITTED,
            )
            db.add(exam)
            await db.flush()
        exam_subjects = []
        for subject in [subjects["dbms"], subjects["os"], subjects["signals"], subjects["ml"]]:
            exam_subject = await get_one(db, ExamSubject, ExamSubject.exam_id == exam.id, ExamSubject.subject_id == subject.id)
            if not exam_subject:
                exam_subject = ExamSubject(
                    exam_id=exam.id,
                    subject_id=subject.id,
                    max_marks=50,
                    pass_marks=20,
                    exam_date=date(2026, 7, 20),
                )
                db.add(exam_subject)
                await db.flush()
            exam_subjects.append(exam_subject)

        for exam_subject in exam_subjects:
            eligible_students = [
                student for student in students
                if await get_one(
                    db,
                    StudentAcademicRecord,
                    StudentAcademicRecord.student_id == student.id,
                    StudentAcademicRecord.academic_year_id == current_year.id,
                )
            ][:8]
            for idx, student in enumerate(eligible_students):
                mark = await get_one(db, Mark, Mark.exam_subject_id == exam_subject.id, Mark.student_id == student.id)
                if not mark:
                    db.add(Mark(
                        exam_subject_id=exam_subject.id,
                        student_id=student.id,
                        marks_obtained=None if idx == 6 else 28 + (idx * 3 % 18),
                        is_absent=idx == 6,
                        is_locked=False,
                    ))
                else:
                    mark.marks_obtained = None if idx == 6 else 28 + (idx * 3 % 18)
                    mark.is_absent = idx == 6

        fee_types = []
        for name, desc in [
            ("Tuition Fee", "Semester tuition fee"),
            ("Laboratory Fee", "Lab maintenance and consumables"),
            ("Library Fee", "Annual library access and services"),
        ]:
            fee_type = await get_one(db, FeeType, FeeType.institution_id == inst.id, FeeType.name == name)
            if not fee_type:
                fee_type = FeeType(institution_id=inst.id, name=name, description=desc)
                db.add(fee_type)
                await db.flush()
            else:
                fee_type.description = desc
            fee_types.append(fee_type)

        fee_structures = []
        for fee_type, course, amount, frequency in [
            (fee_types[0], btech, 75000, "semester"),
            (fee_types[1], btech, 8500, "semester"),
            (fee_types[2], btech, 3000, "annual"),
            (fee_types[0], mtech, 95000, "semester"),
            (fee_types[1], mtech, 12000, "semester"),
        ]:
            structure = await get_one(
                db,
                FeeStructure,
                FeeStructure.fee_type_id == fee_type.id,
                FeeStructure.course_id == course.id,
                FeeStructure.academic_year_id == current_year.id,
            )
            if not structure:
                structure = FeeStructure(
                    fee_type_id=fee_type.id,
                    course_id=course.id,
                    academic_year_id=current_year.id,
                    amount=amount,
                    frequency=frequency,
                )
                db.add(structure)
                await db.flush()
            else:
                structure.amount = amount
                structure.frequency = frequency
            fee_structures.append(structure)

        for idx, student in enumerate(students[:10]):
            structure = fee_structures[0] if idx < 8 else fee_structures[3]
            student_fee = await get_one(db, StudentFee, StudentFee.student_id == student.id, StudentFee.fee_structure_id == structure.id)
            amount_paid = 75000 if idx % 3 == 0 else 35000 if idx % 3 == 1 else 0
            status = FeeStatus.PAID if amount_paid >= float(structure.amount) else FeeStatus.PARTIAL if amount_paid else FeeStatus.UNPAID
            if not student_fee:
                student_fee = StudentFee(
                    student_id=student.id,
                    fee_structure_id=structure.id,
                    amount_due=structure.amount,
                    amount_paid=amount_paid,
                    status=status,
                    due_date=date(2026, 8, 15),
                )
                db.add(student_fee)
                await db.flush()
            else:
                student_fee.amount_due = structure.amount
                student_fee.amount_paid = amount_paid
                student_fee.status = status
                student_fee.due_date = date(2026, 8, 15)
            if amount_paid:
                payment = await get_one(db, FeePayment, FeePayment.student_fee_id == student_fee.id, FeePayment.transaction_ref == f"DEMO-FEE-{idx+1:03d}")
                if not payment:
                    db.add(FeePayment(
                        student_fee_id=student_fee.id,
                        amount=amount_paid,
                        payment_mode="upi" if idx % 2 else "card",
                        transaction_ref=f"DEMO-FEE-{idx+1:03d}",
                        paid_at=datetime(2026, 7, 10 + idx, 10, 30, tzinfo=timezone.utc),
                    ))

        books = []
        for isbn, title, author, publisher, total, available in [
            ("9780132350884", "Clean Code", "Robert C. Martin", "Prentice Hall", 8, 6),
            ("9780262033848", "Introduction to Algorithms", "Cormen, Leiserson, Rivest, Stein", "MIT Press", 6, 4),
            ("9780131103627", "The C Programming Language", "Brian W. Kernighan and Dennis M. Ritchie", "Prentice Hall", 5, 4),
            ("9781491954249", "Designing Data-Intensive Applications", "Martin Kleppmann", "O'Reilly Media", 4, 3),
            ("9789332543515", "Signals and Systems", "Alan V. Oppenheim", "Pearson", 5, 5),
        ]:
            book = await get_one(db, Book, Book.isbn == isbn)
            if not book:
                book = Book(
                    institution_id=inst.id,
                    isbn=isbn,
                    title=title,
                    author=author,
                    publisher=publisher,
                    total_copies=total,
                    available_copies=available,
                )
                db.add(book)
                await db.flush()
            else:
                book.title = title
                book.author = author
                book.publisher = publisher
                book.total_copies = total
                book.available_copies = available
            books.append(book)

        for idx, (book, student) in enumerate(zip(books[:4], students[:4])):
            issue = await get_one(db, BookIssue, BookIssue.book_id == book.id, BookIssue.student_id == student.id, BookIssue.status == IssueStatus.ISSUED)
            if not issue:
                db.add(BookIssue(
                    book_id=book.id,
                    student_id=student.id,
                    issued_on=date(2026, 7, 5 + idx),
                    due_date=date(2026, 7, 19 + idx),
                    fine_amount=0,
                    status=IssueStatus.ISSUED,
                ))

        old_record = await get_one(
            db,
            StudentAcademicRecord,
            StudentAcademicRecord.student_id == students[0].id,
            StudentAcademicRecord.academic_year_id == previous_year.id,
        )
        if not old_record:
            db.add(StudentAcademicRecord(
                student_id=students[0].id,
                section_id=cse_a.id,
                branch_id=cse.id,
                academic_year_id=previous_year.id,
                status=StudentStatus.TRANSFERRED,
                enrolled_at=datetime(2025, 7, 1, tzinfo=timezone.utc),
                exited_at=datetime(2026, 6, 30, tzinfo=timezone.utc),
            ))

        await db.commit()
        print("Seed complete (idempotent).")
        print("   Email   : admin@erp.com")
        print("   Password: Admin@123")
        print(f"   Org ID  : {org.id}")
        print(f"   Inst ID : {inst.id}")


if __name__ == "__main__":
    asyncio.run(seed())
