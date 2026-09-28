import asyncio

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.security import hash_password
from app.db.session import async_session_maker, engine
from app.models.identity import Permission, Role, User

PERMISSIONS: dict[str, str] = {
    "admin:manage": "Manage platform-level administration and RBAC resources.",
    "agent:read": "Read Agent definitions.",
    "agent:create": "Create Agent definitions.",
    "agent:update": "Update Agent definitions.",
    "run:create": "Create Agent or Workflow runs.",
    "run:cancel": "Cancel authorized runs.",
    "skill:read": "Read Skill definitions.",
    "skill:execute": "Execute authorized Skills.",
    "workspace:read": "Read authorized Run workspaces.",
    "artifact:read": "Read authorized Run artifacts.",
    "experiment:read": "Read experiment records through enterprise capabilities.",
    "experiment:create": "Create experiment records through enterprise capabilities.",
    "approval:approve": "Approve policy-gated operations.",
    "eval:run": "Execute Agent evaluation suites.",
}

ROLE_DEFINITIONS: dict[str, tuple[str, set[str]]] = {
    "admin": (
        "Platform administrator with all current permissions.",
        set(PERMISSIONS),
    ),
    "agent_developer": (
        "Builds, runs, and evaluates Agents and their capabilities.",
        {
            "agent:read",
            "agent:create",
            "agent:update",
            "run:create",
            "run:cancel",
            "skill:read",
            "skill:execute",
            "workspace:read",
            "artifact:read",
            "experiment:read",
            "experiment:create",
            "eval:run",
        },
    ),
    "business_user": (
        "Runs approved Agents and consumes authorized business outputs.",
        {
            "agent:read",
            "run:create",
            "run:cancel",
            "workspace:read",
            "artifact:read",
            "experiment:read",
        },
    ),
    "approver": (
        "Reviews and decides protected operations.",
        {
            "agent:read",
            "workspace:read",
            "artifact:read",
            "experiment:read",
            "approval:approve",
        },
    ),
}


async def seed() -> None:
    async with async_session_maker() as session:
        permission_result = await session.execute(select(Permission))
        permissions = {item.code: item for item in permission_result.scalars().all()}

        for code, description in PERMISSIONS.items():
            if code not in permissions:
                permission = Permission(code=code, description=description)
                session.add(permission)
                permissions[code] = permission

        await session.flush()

        role_result = await session.execute(
            select(Role).options(selectinload(Role.permissions))
        )
        roles = {item.name: item for item in role_result.scalars().unique().all()}

        for role_name, (description, permission_codes) in ROLE_DEFINITIONS.items():
            role = roles.get(role_name)
            if role is None:
                role = Role(name=role_name, description=description)
                session.add(role)
                roles[role_name] = role
                await session.flush()
            else:
                role.description = description

            role.permissions = [
                permissions[code]
                for code in sorted(permission_codes)
            ]

        username = settings.bootstrap_admin_username.strip()
        password = settings.bootstrap_admin_password

        if bool(username) != bool(password):
            raise ValueError(
                "BOOTSTRAP_ADMIN_USERNAME and BOOTSTRAP_ADMIN_PASSWORD "
                "must either both be set or both be empty"
            )

        if username and password:
            user_result = await session.execute(
                select(User)
                .options(selectinload(User.roles))
                .where(User.username == username)
            )
            user = user_result.scalar_one_or_none()

            if user is None:
                user = User(
                    username=username,
                    email=settings.bootstrap_admin_email.strip() or None,
                    password_hash=hash_password(password),
                    is_active=True,
                    roles=[roles["admin"]],
                )
                session.add(user)
            elif all(role.name != "admin" for role in user.roles):
                user.roles.append(roles["admin"])

        await session.commit()


async def main() -> None:
    try:
        await seed()
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
