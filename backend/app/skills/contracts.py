from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


@dataclass(slots=True)
class SkillExecutionContext:
    run_id: UUID | None = None
    principal_id: UUID | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class SkillErrorEnvelope(BaseModel):
    code: str
    retryable: bool
    message: str


class SkillExecutionResult(BaseModel):
    call_id: str
    skill_name: str
    ok: bool
    output: Any = None
    error: SkillErrorEnvelope | None = None
    attempts: int = 1
    duration_ms: float = 0.0
    metadata: dict[str, Any] = Field(default_factory=dict)
