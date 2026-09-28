from typing import Any

from pydantic import BaseModel, Field


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
