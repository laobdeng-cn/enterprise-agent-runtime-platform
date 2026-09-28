from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.security import verify_password
from app.models.identity import Role, User


def permission_codes(user: User) -> set[str]:
    return {
        permission.code
        for role in user.roles
        for permission in role.permissions
    }


async def get_user_by_id(session: AsyncSession, user_id: UUID) -> User | None:
    statement = (
        select(User)
        .options(selectinload(User.roles).selectinload(Role.permissions))
        .where(User.id == user_id)
    )
    result = await session.execute(statement)
    return result.scalar_one_or_none()


async def authenticate_user(
    session: AsyncSession,
    username: str,
    password: str,
) -> User | None:
    statement = (
        select(User)
        .options(selectinload(User.roles).selectinload(Role.permissions))
        .where(User.username == username)
    )
    result = await session.execute(statement)
    user = result.scalar_one_or_none()

    if user is None or not user.is_active:
        return None

    if not verify_password(password, user.password_hash):
        return None

    return user
