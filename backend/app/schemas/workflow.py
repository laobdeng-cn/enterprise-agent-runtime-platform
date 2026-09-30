from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class WorkflowNodeDefinition(BaseModel):
    node_key: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=128)
    role: str
    agent_id: UUID
    depends_on: list[str] = Field(default_factory=list)
    condition: dict[str, Any] = Field(default_factory=dict)
    instructions: str = ""
    timeout_seconds: int = Field(default=120, ge=5, le=1800)
    max_attempts: int = Field(default=2, ge=1, le=5)


class WorkflowVersionConfig(BaseModel):
    input_schema: dict[str, Any] = Field(default_factory=dict)
    output_schema: dict[str, Any] = Field(default_factory=dict)
    concurrency_limit: int = Field(default=3, ge=1, le=16)
    nodes: list[WorkflowNodeDefinition]


class WorkflowCreate(WorkflowVersionConfig):
    name: str = Field(min_length=1, max_length=128)
    description: str = ""


class WorkflowVersionCreate(WorkflowVersionConfig):
    pass


class WorkflowRunCreate(BaseModel):
    workflow_id: UUID
    input_data: dict[str, Any] = Field(default_factory=dict)


class WorkflowNodeResponse(BaseModel):
    id: UUID
    node_key: str
    name: str
    role: str
    agent_id: UUID
    depends_on: list[str]
    condition: dict[str, Any]
    instructions: str
    timeout_seconds: int
    max_attempts: int
    position: int


class WorkflowVersionResponse(BaseModel):
    id: UUID
    version: int
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
    concurrency_limit: int
    nodes: list[WorkflowNodeResponse]


class WorkflowResponse(BaseModel):
    id: UUID
    name: str
    description: str
    status: str
    active_version_id: UUID | None
    versions: list[WorkflowVersionResponse]


class WorkflowNodeRunResponse(BaseModel):
    id: UUID
    workflow_node_id: UUID
    node_key: str
    role: str
    position: int
    status: str
    attempt: int
    agent_run_id: UUID | None
    input_data: dict[str, Any]
    output_data: dict[str, Any] | None
    error_data: dict[str, Any] | None
    started_at: datetime | None
    completed_at: datetime | None


class WorkflowCheckpointResponse(BaseModel):
    id: UUID
    sequence: int
    state: str
    kind: str
    payload: dict[str, Any]
    created_at: datetime


class WorkflowRunResponse(BaseModel):
    id: UUID
    workflow_id: UUID
    workflow_version_id: UUID
    created_by_user_id: UUID
    status: str
    input_data: dict[str, Any]
    permission_snapshot: list[str]
    result_data: dict[str, Any] | None
    error_data: dict[str, Any] | None
    state_version: int
    cancel_requested: bool
    created_at: datetime
    started_at: datetime | None
    updated_at: datetime
    completed_at: datetime | None
    node_runs: list[WorkflowNodeRunResponse] = Field(default_factory=list)
    checkpoints: list[WorkflowCheckpointResponse] = Field(default_factory=list)
