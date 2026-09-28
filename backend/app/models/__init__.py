"""Persistence model registry."""

from app.models.agent import Agent, AgentVersion
from app.models.identity import Permission, Role, User, role_permissions, user_roles

__all__ = [
    "Agent",
    "AgentVersion",
    "Permission",
    "Role",
    "User",
    "role_permissions",
    "user_roles",
]
