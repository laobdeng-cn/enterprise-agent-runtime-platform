from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from app.agents.harness.contracts import TokenUsage


class AgentVersionConfig(BaseModel):
    system_instructions: str = Field(min_length=1, max_length=50000)
    model_provider: Literal["deepseek"] = "deepseek"
    model_name: str = Field(default="deepseek-chat", min_length=1, max_length=128)
    temperature: float | None = Field(default=0.2, ge=0.0, le=2.0)
    max_tokens: int | None = Field(default=None, ge=1, le=65536)
    context_policy: dict[str, object] = Field(default_factory=dict)


class AgentCreate(AgentVersionConfig):
    name: str = Field(min_length=1, max_length=128)
    description: str = Field(default="", max_length=10000)


class AgentVersionCreate(AgentVersionConfig):
    pass


class AgentVersionResponse(BaseModel):
    id: UUID
    version: int
    system_instructions: str
    model_provider: str
    model_name: str
    temperature: float | None
    max_tokens: int | None
    context_policy: dict[str, object]


class AgentResponse(BaseModel):
    id: UUID
    name: str
    description: str
    status: str
    active_version_id: UUID | None
    versions: list[AgentVersionResponse]


class AgentInvokeRequest(BaseModel):
    input: str = Field(min_length=1, max_length=100000)
    additional_context: list[str] = Field(default_factory=list, max_length=20)


class AgentInvokeResponse(BaseModel):
    agent_id: UUID
    agent_version_id: UUID
    agent_version: int
    content: str
    provider: str
    model: str
    finish_reason: str | None
    usage: TokenUsage
    duration_ms: float
