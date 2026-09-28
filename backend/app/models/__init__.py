"""Persistence model registry."""

from app.models.identity import Permission, Role, User, role_permissions, user_roles

__all__ = [
    "Permission",
    "Role",
    "User",
    "role_permissions",
    "user_roles",
]
