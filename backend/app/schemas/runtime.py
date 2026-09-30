from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.agents.harness.contracts import ContextTrace


class RunCreate(BaseModel):
    agent_id: UUID
    agent_version_id: UUID | None = None
    input: str = Field(min_length=1, max_length=100000)
    additional_context: list[str] = Field(default_factory=list, max_length=20)
    max_attempts: int = Field(default=2, ge=1, le=5)


class RunStepResponse(BaseModel):
    id: UUID
    sequence: int
    step_type: str
    status: str
    attempt: int
    input_data: dict[str, Any]
    output_data: dict[str, Any] | None
    error_data: dict[str, Any] | None
    started_at: datetime
    completed_at: datetime | None


class ToolCallResponse(BaseModel):
    id: UUID
    provider_call_id: str
    skill_name: str
    skill_version_id: UUID | None
    arguments: dict[str, Any]
    result_data: dict[str, Any] | None
    error_data: dict[str, Any] | None
    status: str
    attempts: int
    duration_ms: float
    created_at: datetime


class RunCheckpointResponse(BaseModel):
    id: UUID
    sequence: int
    state: str
    kind: str
    payload: dict[str, Any]
    created_at: datetime


class RunEventResponse(BaseModel):
    id: UUID
    sequence: int
    event_type: str
    data: dict[str, Any]
    created_at: datetime


class RunResponse(BaseModel):
    id: UUID
    agent_id: UUID
    agent_version_id: UUID
    created_by_user_id: UUID
    status: str
    input: str
    additional_context: list[str]
    permission_snapshot: list[str]
    result_data: dict[str, Any] | None
    error_data: dict[str, Any] | None
    attempt: int
    max_attempts: int
    state_version: int
    pause_requested: bool
    cancel_requested: bool
    created_at: datetime
    started_at: datetime | None
    updated_at: datetime
    completed_at: datetime | None
    steps: list[RunStepResponse] = Field(default_factory=list)
    tool_calls: list[ToolCallResponse] = Field(default_factory=list)
    checkpoints: list[RunCheckpointResponse] = Field(default_factory=list)


class ContextInspectionResponse(BaseModel):
    run_id: UUID
    agent_version_id: UUID
    source: str
    trace: ContextTrace
