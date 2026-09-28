from collections.abc import Awaitable, Callable
from typing import Any

from app.models.skill import SkillVersion
from app.skills.errors import SkillProviderConfigurationError
from app.skills.providers.base import SkillProviderAdapter

LocalSkillHandler = Callable[[dict[str, Any]], Awaitable[Any]]


class LocalSkillAdapter(SkillProviderAdapter):
    def __init__(self, handlers: dict[str, LocalSkillHandler]) -> None:
        self.handlers = handlers

    async def execute(
        self,
        version: SkillVersion,
        arguments: dict[str, Any],
    ) -> Any:
        handler_name = str(version.provider_config.get("handler") or "")
        handler = self.handlers.get(handler_name)
        if handler is None:
            raise SkillProviderConfigurationError(
                f"Local Skill handler '{handler_name}' is not registered"
            )
        return await handler(arguments)
