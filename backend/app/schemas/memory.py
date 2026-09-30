import json
from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.memory.contracts import MemoryScope, MemoryStatus, MemoryType


def _validate_metadata(value: dict[str, Any]) -> dict[str, Any]:
    if len(value) > 64:
        raise ValueError("Memory metadata cannot contain more than 64 keys")
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    if len(encoded) > 16 * 1024:
        raise ValueError("Memory metadata cannot exceed 16 KiB")
    return value


class MemoryCreateRequest(BaseModel):
    memory_type: MemoryType
    scope: MemoryScope
    content: str = Field(min_length=1, max_length=20_000)
    label: str | None = Field(default=None, max_length=128)
    agent_id: UUID | None = None
    run_id: UUID | None = None
    importance: float = Field(default=0.5, ge=0.0, le=1.0)
    ttl_seconds: int | None = Field(
        default=None,
        ge=60,
        le=365 * 24 * 60 * 60,
    )
    metadata: dict[str, Any] = Field(default_factory=dict)

    _metadata_guard = field_validator("metadata")(_validate_metadata)


class MemoryUpdateRequest(BaseModel):
    content: str | None = Field(default=None, min_length=1, max_length=20_000)
    label: str | None = Field(default=None, max_length=128)
    importance: float | None = Field(default=None, ge=0.0, le=1.0)
    status: MemoryStatus | None = None
    metadata: dict[str, Any] | None = None

    @field_validator("metadata")
    @classmethod
    def validate_metadata(
        cls,
        value: dict[str, Any] | None,
    ) -> dict[str, Any] | None:
        return _validate_metadata(value) if value is not None else None


class MemoryResponse(BaseModel):
    id: UUID
    owner_user_id: UUID
    agent_id: UUID | None
    run_id: UUID | None
    memory_type: MemoryType
    scope: MemoryScope
    status: MemoryStatus
    label: str | None
    content: str
    metadata: dict[str, Any]
    source: str
    source_ref: str | None
    importance: float
    expires_at: datetime | None
    access_count: int
    last_accessed_at: datetime | None
    created_at: datetime
    updated_at: datetime


class MemorySearchResult(MemoryResponse):
    score: float
