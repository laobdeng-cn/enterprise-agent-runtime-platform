from collections.abc import Awaitable
from typing import Any, Protocol
from uuid import UUID

from app.memory.contracts import MemoryScope, MemoryType
from app.models.skill import SkillVersion
from app.skills.contracts import SkillExecutionContext
from app.skills.errors import (
    SkillExecutionContextError,
    SkillProviderConfigurationError,
    SkillProviderError,
)
from app.skills.providers.base import SkillProviderAdapter


class MemoryCapabilityPort(Protocol):
    def search(
        self,
        *,
        run_id: UUID,
        principal_id: UUID,
        query: str,
        memory_types: set[MemoryType] | None,
        limit: int,
    ) -> Awaitable[list[dict[str, Any]]]: ...

    def write(
        self,
        *,
        run_id: UUID,
        principal_id: UUID,
        memory_type: MemoryType,
        scope: MemoryScope,
        content: str,
        label: str | None,
        importance: float,
        ttl_seconds: int | None,
        metadata: dict[str, Any],
    ) -> Awaitable[dict[str, Any]]: ...


class MemorySkillAdapter(SkillProviderAdapter):
    def __init__(self, capabilities: MemoryCapabilityPort) -> None:
        self.capabilities = capabilities

    async def execute(
        self,
        version: SkillVersion,
        arguments: dict[str, Any],
        context: SkillExecutionContext | None = None,
    ) -> Any:
        if (
            context is None
            or context.run_id is None
            or context.principal_id is None
        ):
            raise SkillExecutionContextError(
                "Memory Skills require a durable Run and principal context"
            )

        action = str(version.provider_config.get("action") or "")

        try:
            if action == "search":
                types_raw = arguments.get("memory_types")
                memory_types = None
                if isinstance(types_raw, list):
                    memory_types = {
                        MemoryType(str(item).upper())
                        for item in types_raw
                    }
                memories = await self.capabilities.search(
                    run_id=context.run_id,
                    principal_id=context.principal_id,
                    query=str(arguments.get("query") or ""),
                    memory_types=memory_types,
                    limit=int(arguments.get("limit") or 8),
                )
                return {"memories": memories}

            if action == "write":
                metadata_raw = arguments.get("metadata")
                metadata = (
                    dict(metadata_raw)
                    if isinstance(metadata_raw, dict)
                    else {}
                )
                label_raw = arguments.get("label")
                ttl_raw = arguments.get("ttl_seconds")
                return await self.capabilities.write(
                    run_id=context.run_id,
                    principal_id=context.principal_id,
                    memory_type=MemoryType(
                        str(arguments["memory_type"]).upper()
                    ),
                    scope=MemoryScope(str(arguments["scope"]).upper()),
                    content=str(arguments["content"]),
                    label=(
                        str(label_raw)
                        if label_raw is not None
                        else None
                    ),
                    importance=float(arguments.get("importance", 0.5)),
                    ttl_seconds=(
                        int(ttl_raw)
                        if ttl_raw is not None
                        else None
                    ),
                    metadata=metadata,
                )
        except (ValueError, PermissionError, LookupError) as exc:
            raise SkillProviderError(str(exc)) from exc

        raise SkillProviderConfigurationError(
            f"Memory Skill action '{action}' is not registered"
        )
