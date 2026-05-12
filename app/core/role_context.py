from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.roles.model import Menu, Permission, Role, RoleMenu, RolePermission, UserRole


ROLE_PRIORITY = [
    "superadmin",
    "admin",
    "principal",
    "hod",
    "teacher",
    "student",
    "parent",
]

ROLE_ALIASES = {
    "super_admin": "superadmin",
    "super admin": "superadmin",
    "superadministrator": "superadmin",
    "administrator": "admin",
    "college admin": "admin",
    "school admin": "admin",
    "institute admin": "admin",
    "institution admin": "admin",
    "principle": "principal",
    "principal": "principal",
    "head of department": "hod",
    "department head": "hod",
    "hod": "hod",
    "faculty": "teacher",
    "lecturer": "teacher",
    "lecture": "teacher",
    "teacher": "teacher",
    "teachers": "teacher",
    "student": "student",
    "students": "student",
    "parent": "parent",
    "guardian": "parent",
}


def normalize_role(value: str | None) -> str:
    raw = str(value or "").strip().lower().replace("-", "_")
    spaced = raw.replace("_", " ")
    return ROLE_ALIASES.get(raw) or ROLE_ALIASES.get(spaced) or raw


def primary_role(slugs: list[str]) -> str | None:
    normalized = {normalize_role(slug) for slug in slugs if slug}
    for role in ROLE_PRIORITY:
        if role in normalized:
            return role
    return sorted(normalized)[0] if normalized else None


def has_any_role(user: dict, roles: set[str]) -> bool:
    allowed = {normalize_role(role) for role in roles}
    user_roles = {normalize_role(role) for role in user.get("roles", [])}
    current = normalize_role(user.get("role"))
    return current in allowed or bool(user_roles & allowed)


async def get_user_role_context(db: AsyncSession, user_id: str) -> dict:
    role_rows = (
        await db.execute(
            select(Role.id, Role.slug, Role.name)
            .join(UserRole, UserRole.role_id == Role.id)
            .where(UserRole.user_id == user_id)
            .order_by(Role.name.asc())
        )
    ).all()
    role_ids = [role_id for role_id, _, _ in role_rows]
    role_slugs = [slug for _, slug, _ in role_rows]
    role_names = [name for _, _, name in role_rows]
    role_candidates = [value for pair in zip(role_slugs, role_names) for value in pair if value]
    canonical_roles = sorted({normalize_role(value) for value in role_candidates if value})
    role = primary_role(role_candidates)

    permissions: list[str] = []
    menus: list[dict] = []
    if role_ids:
        permission_rows = (
            await db.execute(
                select(Permission.code, Permission.module, Permission.action)
                .join(RolePermission, RolePermission.permission_id == Permission.id)
                .where(RolePermission.role_id.in_(role_ids))
                .order_by(Permission.module.asc(), Permission.action.asc())
            )
        ).all()
        permissions = sorted(
            {
                item
                for code, module, action in permission_rows
                for item in (code, f"{module}.{action}")
            }
        )

        menu_rows = (
            await db.execute(
                select(Menu)
                .join(RoleMenu, RoleMenu.menu_id == Menu.id)
                .where(RoleMenu.role_id.in_(role_ids), Menu.is_active == True)
                .distinct()
                .order_by(Menu.order_no.asc(), Menu.label.asc())
            )
        ).scalars().all()
        menus = [
            {
                "id": str(menu.id),
                "label": menu.label,
                "path": menu.route or "",
                "icon": menu.icon or "",
                "order": menu.order_no,
                "roles": canonical_roles,
            }
            for menu in menu_rows
        ]

    return {
        "role": role,
        "roles": canonical_roles,
        "role_slugs": role_slugs,
        "role_names": role_names,
        "permissions": permissions,
        "menus": menus,
    }
