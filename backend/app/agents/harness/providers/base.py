from abc import ABC, abstractmethod

from app.agents.harness.contracts import ModelRequest, ModelResponse


class ModelProvider(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        """Stable provider identifier."""

    @abstractmethod
    async def invoke(self, request: ModelRequest) -> ModelResponse:
        """Execute one normalized model request."""
