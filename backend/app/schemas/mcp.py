from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field


class MCPServerCreate(BaseModel):
    name: str = Field(
        min_length=1,
        max_length=64,
        pattern=r"^[A-Za-z0-9_-]+$",
    )
    description: str = Field(default="", max_length=10000)
    transport: Literal["HTTP_JSONRPC"] = "HTTP_JSONRPC"
    endpoint_url: str = Field(
        min_length=8,
        max_length=512,
        pattern=r"^https?://",
    )
    status: Literal["active", "disabled"] = "active"
    trust_level: Literal["internal", "approved", "external"] = "internal"
    permission_mapping: dict[str, Any] = Field(default_factory=dict)


class MCPServerUpdate(BaseModel):
    description: str | None = Field(default=None, max_length=10000)
    endpoint_url: str | None = Field(
        default=None,
        min_length=8,
        max_length=512,
        pattern=r"^https?://",
    )
    status: Literal["active", "disabled"] | None = None
    trust_level: Literal["internal", "approved", "external"] | None = None
    permission_mapping: dict[str, Any] | None = None


class MCPServerResponse(BaseModel):
    id: UUID
    name: str
    description: str
    transport: str
    endpoint_url: str
    status: str
    trust_level: str
    permission_mapping: dict[str, Any]
    tool_cache: list[dict[str, Any]]
    protocol_version: str | None
    server_info: dict[str, Any]
    last_health_status: str
    last_health_at: datetime | None
    last_discovered_at: datetime | None
    created_at: datetime
    updated_at: datetime


class MCPHealthResponse(BaseModel):
    server_id: UUID
    status: Literal["healthy", "unhealthy"]
    protocol_version: str | None
    server_info: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None


class MCPDiscoveryResponse(BaseModel):
    server: MCPServerResponse
    discovered_tools: int
    synchronized_skills: list[str]
    disabled_skills: list[str]
