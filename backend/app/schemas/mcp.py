from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field, HttpUrl


class MCPServerCreate(BaseModel):
    name: str = Field(
        min_length=1,
        max_length=64,
        pattern=r"^[A-Za-z0-9_-]+$",
    )
    description: str = Field(default="", max_length=10000)
    url: HttpUrl
    transport: Literal["streamable_http"] = "streamable_http"
    trust_level: Literal["first_party", "trusted", "untrusted"] = "trusted"
    timeout_seconds: float = Field(default=20.0, ge=1.0, le=120.0)
    auth_mode: Literal["none", "secret_ref"] = "none"
    secret_ref: str | None = Field(default=None, max_length=255)
    config: dict[str, Any] = Field(default_factory=dict)


class MCPToolResponse(BaseModel):
    id: UUID
    name: str
    description: str
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
    annotations: dict[str, Any]
    required_permissions: list[str]
    side_effect: str
    status: str
    skill_id: UUID | None
    skill_name: str | None
    discovered_at: datetime


class MCPServerResponse(BaseModel):
    id: UUID
    name: str
    description: str
    url: str
    transport: str
    status: str
    trust_level: str
    timeout_seconds: float
    auth_mode: str
    secret_ref: str | None
    config: dict[str, Any]
    last_health_status: str | None
    last_health_error: str | None
    last_health_at: datetime | None
    last_discovered_at: datetime | None
    tools: list[MCPToolResponse] = Field(default_factory=list)


class MCPHealthResponse(BaseModel):
    server_id: UUID
    status: str
    latency_ms: float
    tool_count: int
    error: str | None = None


class MCPDiscoveryResponse(BaseModel):
    server: MCPServerResponse
    discovered_tools: int
    activated_skills: list[str]
    stale_tools: list[str]
