import asyncio
from logging.config import fileConfig
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config
from alembic import context

# Import ALL models so Alembic detects them
from app.db.base import Base
from app.modules.organizations.model import Organization
from app.modules.institutions.model import Institution
from app.modules.users.model import User
from app.modules.roles.model import Role, Permission, UserRole, RolePermission, Menu, RoleMenu
from app.modules.academic.model import AcademicYear, Course, Branch, Subject, Class, Section
from app.modules.students.model import Student, StudentAcademicRecord, StudentDocument
from app.modules.teachers.model import Teacher, TeacherSubject, TeacherClass, TeacherTimetable
from app.modules.attendance.model import AttendanceSession, AttendanceRecord, AttendanceAuditLog
from app.modules.exams.model import Exam, ExamSubject, Mark
from app.modules.fees.model import FeeType, FeeStructure, StudentFee, FeePayment
from app.modules.library.model import Book, BookIssue
from app.modules.logs.model import ActivityLog
from app.modules.notifications.model import NotificationLog
from app.modules.teacher_content.model import StudyMaterial, Assessment, Assignment, AssignmentSubmission

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url, target_metadata=target_metadata, literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection):
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
