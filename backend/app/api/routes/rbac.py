from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import require_permissions
from app.db.session import get_db
from app.models.identity import Permission, User
from app.schemas.rbac import PermissionResponse, RoleResponse
from app.services.rbac import list_roles_with_permissions

router = APIRouter(prefix="/api/rbac", tags=["rbac"])
AdminPrincipal = Annotated[User, Depends(require_permissions("admin:manage"))]


@router.get("/permissions", response_model=list[PermissionResponse])
async def list_permissions(
    _: AdminPrincipal,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> list[PermissionResponse]:
    result = await session.execute(select(Permission).order_by(Permission.code))
    permissions = list(result.scalars().all())
    return [
        PermissionResponse(
            id=permission.id,
            code=permission.code,
            description=permission.description,
        )
        for permission in permissions
    ]


@router.get("/roles", response_model=list[RoleResponse])
async def list_roles(
    _: AdminPrincipal,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> list[RoleResponse]:
    roles = await list_roles_with_permissions(session)
    return [
        RoleResponse(
            id=role.id,
            name=role.name,
            description=role.description,
            permissions=sorted(permission.code for permission in role.permissions),
        )
        for role in roles
    ]
