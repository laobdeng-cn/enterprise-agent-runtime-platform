from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class WorkspaceResponse(BaseModel):
    id: UUID
    run_id: UUID
    status: str
    quota_bytes: int
    max_file_bytes: int
    used_bytes: int
    created_at: datetime


class WorkspaceEntryResponse(BaseModel):
    path: str
    name: str
    type: Literal["file", "directory"]
    size_bytes: int


class WorkspaceTextWriteRequest(BaseModel):
    path: str = Field(min_length=1, max_length=1024)
    content: str = Field(max_length=5_000_000)


class WorkspaceTextResponse(BaseModel):
    path: str
    content: str


class WorkspaceWriteResult(BaseModel):
    path: str
    size_bytes: int
    sha256: str


class ArtifactPublishRequest(BaseModel):
    source_path: str = Field(min_length=1, max_length=1024)
    display_name: str | None = Field(default=None, max_length=255)
    kind: str = Field(default="file", min_length=1, max_length=32)


class ArtifactResponse(BaseModel):
    id: UUID
    workspace_id: UUID
    relative_path: str
    display_name: str
    kind: str
    media_type: str
    size_bytes: int
    sha256: str
    created_by: str
    source_step_id: UUID | None
    created_at: datetime
