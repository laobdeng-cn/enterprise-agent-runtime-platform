from typing import Any, Protocol
from uuid import UUID

from app.models.skill import SkillVersion
from app.skills.contracts import SkillExecutionContext
from app.skills.errors import (
    SkillExecutionContextError,
    SkillProviderConfigurationError,
    SkillProviderError,
)
from app.skills.providers.base import SkillProviderAdapter


class MCPExecutionPort(Protocol):
    async def call(
        self,
        *,
        server_id: UUID,
        tool_name: str,
        arguments: dict[str, Any],
        principal_id: UUID,
        run_id: UUID | None,
    ) -> Any: ...


class MCPSkillAdapter(SkillProviderAdapter):
    def __init__(self, execution: MCPExecutionPort) -> None:
        self.execution = execution

    async def execute(
        self,
        version: SkillVersion,
        arguments: dict[str, Any],
        context: SkillExecutionContext | None = None,
    ) -> Any:
        if context is None or context.principal_id is None:
            raise SkillExecutionContextError(
                "MCP Skills require an authenticated principal context"
            )

        server_raw = version.provider_config.get("server_id")
        tool_raw = version.provider_config.get("tool_name")
        if not server_raw or not tool_raw:
            raise SkillProviderConfigurationError(
                "MCP Skill is missing server_id or tool_name"
            )

        try:
            server_id = UUID(str(server_raw))
        except ValueError as exc:
            raise SkillProviderConfigurationError(
                "MCP Skill has an invalid server_id"
            ) from exc

        try:
            return await self.execution.call(
                server_id=server_id,
                tool_name=str(tool_raw),
                arguments=arguments,
                principal_id=context.principal_id,
                run_id=context.run_id,
            )
        except (LookupError, PermissionError, ValueError) as exc:
            raise SkillProviderError(str(exc)) from exc
