from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.identity import Role


async def list_roles_with_permissions(session: AsyncSession) -> list[Role]:
    statement = select(Role).options(selectinload(Role.permissions)).order_by(Role.name)
    result = await session.execute(statement)
    return list(result.scalars().unique().all())
