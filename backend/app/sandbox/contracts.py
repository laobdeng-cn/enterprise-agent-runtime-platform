from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, Field


class SandboxStatus(StrEnum):
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    TIMED_OUT = "TIMED_OUT"


@dataclass(frozen=True, slots=True)
class SandboxLimits:
    cpu_limit: float
    memory_limit_mb: int
    timeout_seconds: float
    pids_limit: int
    tmpfs_mb: int
    max_output_bytes: int
    max_code_bytes: int


@dataclass(frozen=True, slots=True)
class RawSandboxResult:
    execution_id: UUID
    status: SandboxStatus
    exit_code: int | None
    stdout: str
    stderr: str
    duration_ms: float
    timed_out: bool
    output_relative_path: str
    stdout_truncated: bool = False
    stderr_truncated: bool = False


class SandboxArtifactResponse(BaseModel):
    artifact_id: UUID
    path: str
    display_name: str
    media_type: str
    size_bytes: int
    sha256: str


class SandboxExecutionResponse(BaseModel):
    execution_id: UUID
    run_id: UUID
    status: SandboxStatus
    exit_code: int | None
    stdout: str
    stderr: str
    duration_ms: float
    timed_out: bool
    stdout_truncated: bool = False
    stderr_truncated: bool = False
    artifacts: list[SandboxArtifactResponse] = Field(default_factory=list)


class SandboxExecuteRequest(BaseModel):
    code: str = Field(min_length=1, max_length=100_000)
    publish_artifacts: bool = True
