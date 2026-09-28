from collections.abc import Awaitable
from typing import Any, Protocol
from uuid import UUID

from app.models.skill import SkillVersion
from app.skills.contracts import SkillExecutionContext
from app.skills.errors import (
    SkillExecutionContextError,
    SkillProviderConfigurationError,
)
from app.skills.providers.base import SkillProviderAdapter


class WorkspaceCapabilityPort(Protocol):
    def list_entries(
        self,
        run_id: UUID,
        relative_path: str,
    ) -> Awaitable[list[dict[str, Any]]]: ...

    def read_text(
        self,
        run_id: UUID,
        relative_path: str,
    ) -> Awaitable[dict[str, Any]]: ...

    def write_text(
        self,
        run_id: UUID,
        relative_path: str,
        content: str,
    ) -> Awaitable[dict[str, Any]]: ...

    def publish_artifact(
        self,
        run_id: UUID,
        source_path: str,
        display_name: str | None,
        kind: str,
    ) -> Awaitable[dict[str, Any]]: ...


class WorkspaceSkillAdapter(SkillProviderAdapter):
    def __init__(self, capabilities: WorkspaceCapabilityPort) -> None:
        self.capabilities = capabilities

    async def execute(
        self,
        version: SkillVersion,
        arguments: dict[str, Any],
        context: SkillExecutionContext | None = None,
    ) -> Any:
        if context is None or context.run_id is None:
            raise SkillExecutionContextError(
                "Workspace Skills require a durable Run execution context"
            )

        action = str(version.provider_config.get("action") or "")
        if action == "list":
            entries = await self.capabilities.list_entries(
                context.run_id,
                str(arguments["path"]),
            )
            return {"entries": entries}
        if action == "read_text":
            return await self.capabilities.read_text(
                context.run_id,
                str(arguments["path"]),
            )
        if action == "write_text":
            return await self.capabilities.write_text(
                context.run_id,
                str(arguments["path"]),
                str(arguments["content"]),
            )
        if action == "publish_artifact":
            display_name_raw = arguments.get("display_name")
            display_name = (
                str(display_name_raw)
                if display_name_raw is not None
                else None
            )
            return await self.capabilities.publish_artifact(
                context.run_id,
                str(arguments["source_path"]),
                display_name,
                str(arguments.get("kind") or "file"),
            )
        raise SkillProviderConfigurationError(
            f"Workspace Skill action '{action}' is not registered"
        )
