from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field

from app.skills.contracts import SkillExecutionResult


class SkillVersionConfig(BaseModel):
    input_schema: dict[str, Any] = Field(default_factory=dict)
    output_schema: dict[str, Any] = Field(default_factory=dict)
    required_permissions: list[str] = Field(default_factory=list)
    side_effect: Literal[
        "READ_ONLY",
        "REVERSIBLE_WRITE",
        "IRREVERSIBLE_WRITE",
        "SENSITIVE",
    ] = "READ_ONLY"
    timeout_seconds: int = Field(default=20, ge=1, le=120)
    max_attempts: int = Field(default=1, ge=1, le=3)
    provider_config: dict[str, Any] = Field(default_factory=dict)


class SkillCreate(SkillVersionConfig):
    name: str = Field(
        min_length=1,
        max_length=64,
        pattern=r"^[A-Za-z0-9_-]+$",
    )
    description: str = Field(default="", max_length=10000)
    provider_type: Literal["local"] = "local"


class SkillVersionCreate(SkillVersionConfig):
    pass


class SkillVersionResponse(BaseModel):
    id: UUID
    version: int
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
    required_permissions: list[str]
    side_effect: str
    timeout_seconds: int
    max_attempts: int
    provider_config: dict[str, Any]


class SkillResponse(BaseModel):
    id: UUID
    name: str
    description: str
    provider_type: str
    status: str
    active_version_id: UUID | None
    versions: list[SkillVersionResponse]


class SkillExecuteRequest(BaseModel):
    arguments: dict[str, Any] = Field(default_factory=dict)


class SkillExecuteResponse(BaseModel):
    result: SkillExecutionResult
