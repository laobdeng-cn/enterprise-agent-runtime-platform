from uuid import UUID

from pydantic import BaseModel


class PermissionResponse(BaseModel):
    id: UUID
    code: str
    description: str


class RoleResponse(BaseModel):
    id: UUID
    name: str
    description: str
    permissions: list[str]
