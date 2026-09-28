from collections.abc import Awaitable
from typing import Any, Protocol
from uuid import UUID

from app.models.skill import SkillVersion
from app.sandbox.contracts import SandboxExecutionResponse
from app.sandbox.errors import (
    SandboxCodeTooLargeError,
    SandboxExecutionInfrastructureError,
    SandboxImageError,
    SandboxOutputPolicyError,
    SandboxUnavailableError,
)
from app.skills.contracts import SkillExecutionContext
from app.skills.errors import (
    SkillExecutionContextError,
    SkillProviderConfigurationError,
    SkillProviderError,
    SkillRetryableProviderError,
)
from app.skills.providers.base import SkillProviderAdapter


class SandboxCapabilityPort(Protocol):
    def execute_python(
        self,
        run_id: UUID,
        code: str,
        *,
        publish_outputs: bool = True,
        created_by: str = "agent",
    ) -> Awaitable[SandboxExecutionResponse]: ...


class SandboxSkillAdapter(SkillProviderAdapter):
    def __init__(self, capabilities: SandboxCapabilityPort) -> None:
        self.capabilities = capabilities

    async def execute(
        self,
        version: SkillVersion,
        arguments: dict[str, Any],
        context: SkillExecutionContext | None = None,
    ) -> Any:
        if context is None or context.run_id is None:
            raise SkillExecutionContextError(
                "Sandbox Skills require a durable Run execution context"
            )

        action = str(version.provider_config.get("action") or "")
        if action != "python_execute":
            raise SkillProviderConfigurationError(
                f"Sandbox Skill action '{action}' is not registered"
            )

        try:
            result = await self.capabilities.execute_python(
                context.run_id,
                str(arguments["code"]),
                publish_outputs=bool(arguments.get("publish_artifacts", True)),
                created_by="agent",
            )
        except (
            SandboxUnavailableError,
            SandboxImageError,
            SandboxExecutionInfrastructureError,
        ) as exc:
            raise SkillRetryableProviderError(str(exc)) from exc
        except (
            SandboxCodeTooLargeError,
            SandboxOutputPolicyError,
        ) as exc:
            raise SkillProviderError(str(exc)) from exc

        return result.model_dump(mode="json")
