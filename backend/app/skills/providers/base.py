from abc import ABC, abstractmethod
from typing import Any

from app.models.skill import SkillVersion


class SkillProviderAdapter(ABC):
    @abstractmethod
    async def execute(
        self,
        version: SkillVersion,
        arguments: dict[str, Any],
    ) -> Any:
        """Execute one concrete SkillVersion."""
