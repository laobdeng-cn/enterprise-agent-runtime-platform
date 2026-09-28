from abc import ABC, abstractmethod
from typing import Any

from app.models.skill import SkillVersion
from app.skills.contracts import SkillExecutionContext


class SkillProviderAdapter(ABC):
    @abstractmethod
    async def execute(
        self,
        version: SkillVersion,
        arguments: dict[str, Any],
        context: SkillExecutionContext | None = None,
    ) -> Any:
        """Execute one concrete SkillVersion."""
