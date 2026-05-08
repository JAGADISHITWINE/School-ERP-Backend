from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import delete, select, func
import secrets
import string
from app.modules.users.model import User
from app.modules.roles.model import Role, UserRole
from app.modules.users.schema import UserCreate, UserUpdate
from app.core.security import hash_password
from app.core.exceptions import NotFoundError, ConflictError, ValidationError
from app.utils.mailer import send_email


def _set_user_role_attrs(user: User, role_id=None, role_name=None) -> User:
    user.role_id = role_id
    user.role_name = role_name
    return user


async def _ensure_role_belongs_to_institution(
    db: AsyncSession, role_id: str, institution_id: str
) -> Role:
    role = (
        await db.execute(
            select(Role).where(
                Role.id == role_id,
                Role.institution_id == institution_id,
            )
        )
    ).scalar_one_or_none()
    if not role:
        raise ValidationError("Role not found for selected institution")
    return role


async def _attach_primary_role(db: AsyncSession, user: User) -> User:
    row = (
        await db.execute(
            select(Role.id, Role.name)
            .join(UserRole, UserRole.role_id == Role.id)
            .where(UserRole.user_id == user.id)
            .limit(1)
        )
    ).first()
    if not row:
        return _set_user_role_attrs(user)
    role_id, role_name = row
    return _set_user_role_attrs(user, role_id, role_name)


async def _attach_primary_roles(db: AsyncSession, users: list[User]) -> list[User]:
    if not users:
        return users

    user_ids = [u.id for u in users]
    rows = (
        await db.execute(
            select(UserRole.user_id, Role.id, Role.name)
            .join(Role, Role.id == UserRole.role_id)
            .where(UserRole.user_id.in_(user_ids))
        )
    ).all()

    role_by_user = {}
    for user_id, role_id, role_name in rows:
        role_by_user.setdefault(user_id, (role_id, role_name))

    for user in users:
        role_id, role_name = role_by_user.get(user.id, (None, None))
        _set_user_role_attrs(user, role_id, role_name)

    return users


async def create_user(db: AsyncSession, data: UserCreate) -> User:
    ex = (await db.execute(select(User).where(User.email == data.email))).scalar_one_or_none()
    if ex:
        raise ConflictError("Email already registered")
    ex2 = (await db.execute(select(User).where(User.username == data.username))).scalar_one_or_none()
    if ex2:
        raise ConflictError("Username already taken")
    role = None
    if data.role_id:
        role = await _ensure_role_belongs_to_institution(db, data.role_id, data.institution_id)

    generated_password = data.password or _generate_password()
    user = User(
        institution_id=data.institution_id,
        email=data.email,
        username=data.username,
        password_hash=hash_password(generated_password),
        full_name=data.full_name,
        phone=data.phone,
    )
    db.add(user)
    await db.flush()

    if data.role_id:
        db.add(UserRole(user_id=user.id, role_id=data.role_id))
        await db.flush()

    await db.refresh(user)
    if role:
        _set_user_role_attrs(user, role.id, role.name)
    else:
        _set_user_role_attrs(user)
    setattr(user, "generated_password", generated_password)
    setattr(user, "credentials_dispatched", _send_credentials_email(user.email, user.username, generated_password))
    return user


async def list_users(db: AsyncSession, institution_id: str, offset: int, limit: int):
    q = select(User).where(User.institution_id == institution_id)
    total = (await db.execute(select(func.count()).select_from(q.subquery()))).scalar()
    result = await db.execute(q.offset(offset).limit(limit))
    users = result.scalars().all()
    return await _attach_primary_roles(db, users), total


async def get_user(db: AsyncSession, user_id: str) -> User:
    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if not user:
        raise NotFoundError("User not found")
    return await _attach_primary_role(db, user)


async def update_user(db: AsyncSession, user_id: str, data: UserUpdate) -> User:
    user = await get_user(db, user_id)
    incoming = data.model_dump(exclude_none=True)
    role_id = incoming.pop("role_id", None)

    for k, v in incoming.items():
        setattr(user, k, v)

    role = None
    if role_id:
        role = await _ensure_role_belongs_to_institution(db, role_id, user.institution_id)
        await db.execute(delete(UserRole).where(UserRole.user_id == user.id))
        db.add(UserRole(user_id=user.id, role_id=role_id))

    await db.flush()
    if role:
        _set_user_role_attrs(user, role.id, role.name)
    else:
        await _attach_primary_role(db, user)
    return user


def _generate_password(length: int = 10) -> str:
    alphabet = string.ascii_letters + string.digits + "@#$%&*"
    return "".join(secrets.choice(alphabet) for _ in range(length))


def _send_credentials_email(email: str, password: str) -> bool:
    subject = "Your School ERP Account is Ready"

    html_body = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <meta http-equiv="X-UA-Compatible" content="IE=edge"/>
  <title>Your School ERP Credentials</title>
  <style>
    @import url('https://fonts.googleapis.com/css2?family=Sora:wght@400;500;600;700;800&family=JetBrains+Mono:wght@500&display=swap');
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ background-color: #F4F1EE; font-family: 'Sora', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; -webkit-font-smoothing: antialiased; }}
    .wrapper {{ width: 100%; background-color: #F4F1EE; padding: 40px 16px; }}
    .card {{ max-width: 500px; margin: 0 auto; border-radius: 24px; overflow: hidden; box-shadow: 0 8px 40px rgba(0,0,0,0.10); }}

    /* ── Hero ── */
    .hero {{ background-color: #1B0B3B; padding: 44px 40px 0; position: relative; overflow: hidden; }}
    .hero-circle {{ position: absolute; border-radius: 50%; }}
    .hc1 {{ width: 260px; height: 260px; background: rgba(138,91,255,0.18); top: -80px; right: -60px; }}
    .hc2 {{ width: 160px; height: 160px; background: rgba(255,100,130,0.12); top: 40px; left: -50px; }}
    .hero-top {{ margin-bottom: 32px; }}
    .badge {{ display: inline-block; background: rgba(255,255,255,0.08); border: 1px solid rgba(255,255,255,0.12); border-radius: 100px; padding: 6px 14px; }}
    .badge-dot {{ display: inline-block; width: 8px; height: 8px; border-radius: 50%; background: #50DCA4; vertical-align: middle; margin-right: 7px; }}
    .badge-txt {{ font-size: 11px; font-weight: 600; color: rgba(255,255,255,0.75); letter-spacing: 0.04em; text-transform: uppercase; vertical-align: middle; }}
    .hero h1 {{ font-size: 28px; font-weight: 800; color: #ffffff; line-height: 1.18; letter-spacing: -0.03em; margin-bottom: 10px; position: relative; z-index: 2; }}
    .hero h1 span {{ color: #A87DFF; }}
    .hero-sub {{ font-size: 13px; color: rgba(255,255,255,0.42); line-height: 1.5; margin-bottom: 28px; position: relative; z-index: 2; }}

    /* ── Body ── */
    .body {{ background: #ffffff; padding: 32px 36px 28px; }}
    .pill-label {{ display: inline-block; background: #F3EFFF; border-radius: 100px; padding: 5px 14px; margin-bottom: 16px; }}
    .pill-dot {{ display: inline-block; width: 6px; height: 6px; border-radius: 50%; background: #7C4DFF; vertical-align: middle; margin-right: 6px; }}
    .pill-txt {{ font-size: 10px; font-weight: 700; color: #7C4DFF; text-transform: uppercase; letter-spacing: 0.08em; vertical-align: middle; }}

    .cred-item {{ border-radius: 14px; border: 1.5px solid #EDE8FF; background: #FDFCFF; margin-bottom: 10px; padding: 14px 16px; }}
    .ci-icon {{ display: inline-block; width: 38px; height: 38px; border-radius: 10px; background: #EDE8FF; text-align: center; line-height: 38px; font-size: 17px; vertical-align: middle; }}
    .ci-body {{ display: inline-block; vertical-align: middle; margin-left: 12px; max-width: calc(100% - 120px); }}
    .ci-name {{ font-size: 10px; font-weight: 700; color: #9B8EC4; text-transform: uppercase; letter-spacing: 0.07em; margin-bottom: 3px; }}
    .ci-val {{ font-family: 'JetBrains Mono', 'Courier New', Courier, monospace; font-size: 13px; font-weight: 500; color: #1B0B3B; }}

    .divider {{ height: 1px; background: #F4F0FF; margin: 12px 0 22px; }}

    .notice {{ background: #FFFAF0; border-left: 3px solid #F5B731; border-radius: 0 10px 10px 0; padding: 13px 14px; margin-bottom: 26px; }}
    .notice-icon {{ display: inline-block; font-size: 16px; vertical-align: top; margin-right: 10px; margin-top: 1px; }}
    .notice-text {{ display: inline-block; font-size: 12px; color: #7A5800; line-height: 1.6; font-weight: 500; vertical-align: top; width: calc(100% - 36px); }}

    .cta-btn {{ display: block; text-align: center; background: #1B0B3B; color: #ffffff; font-family: 'Sora', -apple-system, sans-serif; font-size: 14px; font-weight: 700; padding: 15px 28px; border-radius: 14px; text-decoration: none; letter-spacing: -0.01em; margin-bottom: 14px; }}
    .cta-arrow {{ color: #A87DFF; margin-left: 6px; }}
    .help-text {{ font-size: 11.5px; color: #B0A8C8; text-align: center; line-height: 1.65; }}

    /* ── Footer ── */
    .footer {{ background: #FAF8FF; border-top: 1px solid #EDE8FF; padding: 18px 36px; }}
    .footer-brand {{ font-size: 11px; font-weight: 700; color: #9B8EC4; text-transform: uppercase; letter-spacing: 0.06em; }}
    .footer-right {{ font-size: 11px; color: #C5BCDC; text-align: right; }}

    @media only screen and (max-width: 520px) {{
      .hero {{ padding: 32px 24px 0; }}
      .hero h1 {{ font-size: 23px; }}
      .body {{ padding: 24px 22px; }}
      .footer {{ padding: 16px 22px; }}
    }}
  </style>
</head>
<body>
<div class="wrapper">
  <div class="card">

    <!-- Hero -->
    <div class="hero">
      <div class="hero-circle hc1"></div>
      <div class="hero-circle hc2"></div>
      <div class="hero-top">
        <div class="badge">
          <span class="badge-dot"></span>
          <span class="badge-txt">Account created</span>
        </div>
      </div>
      <h1>Your portal<br/>access is <span>live.</span></h1>
      <p class="hero-sub">We've set up your School ERP account.<br/>Your credentials are below — keep them safe.</p>
      <table cellpadding="0" cellspacing="0" width="100%">
        <tr><td>
          <svg viewBox="0 0 500 36" xmlns="http://www.w3.org/2000/svg" preserveAspectRatio="none" height="36" width="100%" style="display:block;">
            <path d="M0,36 C120,0 300,36 500,10 L500,36 Z" fill="#ffffff"/>
          </svg>
        </td></tr>
      </table>
    </div>

    <!-- Body -->
    <div class="body">
      <div class="pill-label">
        <span class="pill-dot"></span>
        <span class="pill-txt">Login credentials</span>
      </div>

      <!-- Email -->
      <div class="cred-item">
        <span class="ci-icon">&#128231;</span>
        <div class="ci-body">
          <div class="ci-name">Email / Username</div>
          <div class="ci-val">{email}</div>
        </div>
      </div>

      <!-- Password -->
      <div class="cred-item">
        <span class="ci-icon">&#128273;</span>
        <div class="ci-body">
          <div class="ci-name">Temporary password</div>
          <div class="ci-val">{password}</div>
        </div>
      </div>

      <div class="divider"></div>

      <!-- Warning -->
      <div class="notice">
        <span class="notice-icon">&#9888;&#65039;</span>
        <span class="notice-text">You'll be asked to set a new password on first sign-in. Never share these credentials with anyone else.</span>
      </div>

      <!-- CTA -->
      <a href="https://your-school-erp-url.com/login" class="cta-btn">
        Sign in to School ERP <span class="cta-arrow">&#8599;</span>
      </a>

      <p class="help-text">Didn't expect this email? Contact your school admin or IT helpdesk.</p>
    </div>

    <!-- Footer -->
    <div class="footer">
      <table cellpadding="0" cellspacing="0" width="100%">
        <tr>
          <td class="footer-brand">&#127891; School ERP</td>
          <td class="footer-right">&copy; 2026 &bull; No-reply</td>
        </tr>
      </table>
    </div>

  </div>
</div>
</body>
</html>"""

    plain_body = (
        "Your School ERP account is ready.\n\n"
        f"Email: {email}\n"
        f"Password: {password}\n\n"
        "You'll be prompted to set a new password on first sign-in.\n"
        "Keep these credentials private.\n\n"
        "Didn't expect this? Contact your school admin or IT helpdesk."
    )

    return send_email(email, subject, html_body=html_body, plain_body=plain_body)