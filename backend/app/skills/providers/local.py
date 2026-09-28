from collections.abc import Awaitable, Callable, Mapping
from typing import Any

from app.models.skill import SkillVersion
from app.skills.errors import SkillProviderConfigurationError
from app.skills.providers.base import SkillProviderAdapter

LocalSkillHandler = Callable[[dict[str, Any]], Awaitable[Any]]


class LocalSkillAdapter(SkillProviderAdapter):
    def __init__(self, handlers: Mapping[str, LocalSkillHandler]) -> None:
        self.handlers = dict(handlers)

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
