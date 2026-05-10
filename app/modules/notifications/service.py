import os
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.modules.attendance.model import AttendanceSession, AttendanceStatus
from app.modules.academic.model import Section, Subject
from app.modules.notifications.model import NotificationLog, NotificationChannel, NotificationStatus
from app.modules.students.model import Student
from app.modules.teachers.model import Teacher
from app.modules.users.model import User
from app.utils.mailer import send_email


async def list_notifications(db: AsyncSession, institution_id: str | None, offset: int, limit: int):
    q = select(NotificationLog)
    if institution_id:
        q = q.where(NotificationLog.institution_id == institution_id)
    total = (await db.execute(select(func.count()).select_from(q.subquery()))).scalar() or 0
    rows = (
        await db.execute(
            q.order_by(NotificationLog.created_at.desc()).offset(offset).limit(limit)
        )
    ).scalars().all()
    return rows, total


async def create_notification_log(
    db: AsyncSession,
    *,
    institution_id,
    student_id=None,
    attendance_session_id=None,
    channel: NotificationChannel,
    recipient: str | None,
    subject: str | None,
    body: str | None,
    provider: str | None,
    dedupe_key: str | None = None,
) -> NotificationLog:
    if dedupe_key:
        existing = (
            await db.execute(select(NotificationLog).where(NotificationLog.dedupe_key == dedupe_key))
        ).scalar_one_or_none()
        if existing:
            return existing

    status = NotificationStatus.PENDING if recipient else NotificationStatus.SKIPPED
    item = NotificationLog(
        institution_id=institution_id,
        student_id=student_id,
        attendance_session_id=attendance_session_id,
        channel=channel,
        recipient=recipient,
        subject=subject,
        body=body,
        provider=provider,
        dedupe_key=dedupe_key,
        status=status,
        error_message=None if recipient else "Recipient not configured",
    )
    db.add(item)
    await db.flush()
    return item


async def send_absent_alerts(
    db: AsyncSession,
    *,
    session: AttendanceSession,
    absent_student_ids: list,
) -> int:
    if not absent_student_ids:
        return 0

    context = (
        await db.execute(
            select(Section.name, Subject.name, User.institution_id)
            .select_from(AttendanceSession)
            .join(Section, Section.id == AttendanceSession.section_id)
            .join(Subject, Subject.id == AttendanceSession.subject_id)
            .join(Teacher, Teacher.id == AttendanceSession.teacher_id)
            .join(User, User.id == Teacher.user_id)
            .where(AttendanceSession.id == session.id)
        )
    ).first()
    section_name = context[0] if context else "class"
    subject_name = context[1] if context else "scheduled class"
    institution_id = context[2] if context else None

    rows = (
        await db.execute(
            select(Student, User.full_name, User.email)
            .join(User, User.id == Student.user_id)
            .where(Student.id.in_(absent_student_ids))
        )
    ).all()

    created = 0
    for student, full_name, student_email in rows:
        guardian_email = getattr(student, "guardian_email", None) or student_email
        guardian_phone = student.guardian_phone
        subject = f"Attendance alert: {full_name} absent"
        plain_body = (
            f"Dear {student.guardian_name or 'Parent'},\n\n"
            f"{full_name} was marked absent for {subject_name} in {section_name} "
            f"on {session.session_date}.\n\n"
            "Regards,\nCollege Administration"
        )
        html_body = plain_body.replace("\n", "<br>")
        sms_body = f"{full_name} was marked absent for {subject_name} on {session.session_date}."

        email_log = await create_notification_log(
            db,
            institution_id=institution_id,
            student_id=student.id,
            attendance_session_id=session.id,
            channel=NotificationChannel.EMAIL,
            recipient=guardian_email,
            subject=subject,
            body=plain_body,
            provider="smtp",
            dedupe_key=f"attendance:{session.id}:{student.id}:email:absent",
        )
        if email_log.status == NotificationStatus.PENDING:
            ok = send_email(guardian_email, subject, html_body, plain_body) if guardian_email else False
            email_log.status = NotificationStatus.SENT if ok else NotificationStatus.FAILED
            email_log.error_message = None if ok else "SMTP not configured or email delivery failed"
            created += 1

        sms_log = await create_notification_log(
            db,
            institution_id=institution_id,
            student_id=student.id,
            attendance_session_id=session.id,
            channel=NotificationChannel.SMS,
            recipient=guardian_phone,
            subject="Attendance alert",
            body=sms_body,
            provider=os.getenv("SMS_PROVIDER", "not_configured"),
            dedupe_key=f"attendance:{session.id}:{student.id}:sms:absent",
        )
        if sms_log.status == NotificationStatus.PENDING:
            sms_log.status = NotificationStatus.SKIPPED
            sms_log.error_message = "SMS provider not configured"
            created += 1

    await db.flush()
    return created
