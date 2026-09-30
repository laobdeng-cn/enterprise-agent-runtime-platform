from typing import Any

from pydantic import BaseModel, Field


class MCPRemoteTool(BaseModel):
    name: str
    description: str = ""
    input_schema: dict[str, Any] = Field(default_factory=dict)
    output_schema: dict[str, Any] = Field(default_factory=dict)
    annotations: dict[str, Any] = Field(default_factory=dict)


class MCPHealthResult(BaseModel):
    status: str
    latency_ms: float
    tool_count: int
    error: str | None = None
