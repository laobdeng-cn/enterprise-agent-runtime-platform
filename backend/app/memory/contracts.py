from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID


class MemoryType(StrEnum):
    CONVERSATION = "CONVERSATION"
    TASK = "TASK"
    LONG_TERM = "LONG_TERM"
    SEMANTIC = "SEMANTIC"


class MemoryScope(StrEnum):
    USER = "USER"
    AGENT = "AGENT"
    RUN = "RUN"


class MemoryStatus(StrEnum):
    ACTIVE = "ACTIVE"
    ARCHIVED = "ARCHIVED"
    DELETED = "DELETED"


class MemorySource(StrEnum):
    USER = "USER"
    AGENT = "AGENT"
    SYSTEM = "SYSTEM"
    TOOL = "TOOL"


@dataclass(frozen=True, slots=True)
class MemoryMatch:
    id: UUID
    memory_type: MemoryType
    scope: MemoryScope
    content: str
    score: float
    importance: float
    source: MemorySource
